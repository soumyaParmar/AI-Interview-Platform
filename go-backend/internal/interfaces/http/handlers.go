package http

import (
	"devsko-ai-interview/internal/infrastructure/database"
	"devsko-ai-interview/internal/domain/entities"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

func CreateJD(c *fiber.Ctx) error {
	type Request struct {
		RawText string `json:"raw_text"`
	}
	var req Request
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Invalid request body"})
	}

	jd := entities.JobDescription{
		RawText: req.RawText,
	}

	if err := database.DB.Create(&jd).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	return c.JSON(fiber.Map{"id": jd.ID})
}

func CreateSession(c *fiber.Ctx) error {
	type Request struct {
		JDID          string `json:"jd_id"`
		CandidateName string `json:"candidate_name"`
		ResumeText    string `json:"resume_text"`
	}
	var req Request
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Invalid request body"})
	}

	urlSlug := uuid.New().String()[:8]
	session := entities.InterviewSession{
		JDID:          req.JDID,
		CandidateName: req.CandidateName,
		ResumeText:    req.ResumeText,
		ShareURLSlug:  urlSlug,
	}

	if err := database.DB.Create(&session).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	return c.JSON(fiber.Map{"id": session.ID, "share_url_slug": urlSlug})
}

func GetSessionReport(c *fiber.Ctx) error {
	slug := c.Params("slug")
	var session entities.InterviewSession
	if err := database.DB.Where("share_url_slug = ?", slug).First(&session).Error; err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "Session not found"})
	}

	if session.FinalReport == nil {
		return c.Status(404).JSON(fiber.Map{"error": "Report not generated yet"})
	}

	return c.Send(session.FinalReport)
}
