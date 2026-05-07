package socket

import (
	"devsko-ai-interview/internal/infrastructure/aiclient"
	"devsko-ai-interview/internal/infrastructure/database"
	"devsko-ai-interview/internal/domain/entities"
	"devsko-ai-interview/internal/infrastructure/cache"
	"devsko-ai-interview/pkg/utils"
	"encoding/json"
	"fmt"
	"log"

	socketio "github.com/googollee/go-socket.io"
)

func SetupSocketHandlers(server *socketio.Server) {
	server.OnConnect("/", func(s socketio.Conn) error {
		s.SetContext("")
		log.Println("connected:", s.ID())
		return nil
	})

	server.OnEvent("/", "join_interview", func(s socketio.Conn, data map[string]interface{}) {
		sessionSlug := data["session_slug"].(string)
		log.Printf("Client %s joining session %s", s.ID(), sessionSlug)

		var session entities.InterviewSession
		if err := database.DB.Where("share_url_slug = ?", sessionSlug).First(&session).Error; err != nil {
			s.Emit("error", map[string]string{"message": "Session not found"})
			return
		}

		state, err := cache.GetSessionState(sessionSlug)
		if err != nil {
			var skillMaps []entities.SkillMap
			database.DB.Where("session_id = ?", session.ID).Find(&skillMaps)
			
			state = map[string]interface{}{
				"phase":         "VERIFICATION",
				"skill_index":   0,
				"total_skills":  len(skillMaps),
				"depth":         0,
				"current_topic": "Professional Experience",
			}
			cache.SetSessionState(sessionSlug, state)
		}

		s.Join(sessionSlug)
		s.Emit("discovery_status", map[string]string{"status": fmt.Sprintf("Phase: %v - Topic: %v", state["phase"], state["current_topic"])})
		
		welcomeMsg := "Hello! I'm your interviewer today. Let's get started. First, could you tell me about your technical background?"
		s.Emit("agent_response", map[string]string{"content": welcomeMsg})
		s.Emit("transcript_update", map[string]string{"role": "agent", "content": welcomeMsg})

		database.DB.Create(&entities.Transcript{
			SessionID: session.ID,
			Role:      "agent",
			Content:   welcomeMsg,
		})
	})

	server.OnEvent("/", "user_answer", func(s socketio.Conn, data map[string]interface{}) {
		sessionSlug := data["session_slug"].(string)
		userText := data["text"].(string)

		var session entities.InterviewSession
		database.DB.Where("share_url_slug = ?", sessionSlug).First(&session)

		database.DB.Create(&entities.Transcript{
			SessionID: session.ID,
			Role:      "user",
			Content:   userText,
		})

		s.Emit("transcript_update", map[string]string{"role": "user", "content": userText})
		s.Emit("status_update", map[string]string{"status": "Thinking"})

		go func() {
			state, _ := cache.GetSessionState(sessionSlug)
			depth := int(state["depth"].(float64)) + 1
			state["depth"] = depth
			cache.SetSessionState(sessionSlug, state)

			var transcripts []entities.Transcript
			database.DB.Where("session_id = ?", session.ID).Order("timestamp asc").Find(&transcripts)
			
			var history []aiclient.Message
			for _, t := range transcripts {
				role := "user"
				if t.Role == "agent" {
					role = "assistant"
				}
				history = append(history, aiclient.Message{Role: role, Content: t.Content})
			}

			resumeText := "N/A"
			if session.ResumeText != "" {
				resumeText = session.ResumeText
			}

			var jd entities.JobDescription
			database.DB.First(&jd, "id = ?", session.JDID)

			systemPrompt := fmt.Sprintf(utils.INTERVIEWER_SYSTEM_PROMPT, 
				"Senior Tech Recruiter",
				jd.RawText,
				resumeText,
				state["phase"],
				state["current_topic"],
				depth,
			)

			messages := append([]aiclient.Message{{Role: "system", Content: systemPrompt}}, history...)
			s.Emit("status_update", map[string]string{"status": "Analyzing"})
			
			aiResp, err := aiclient.GetAIResponse(messages, false)
			if err != nil {
				s.Emit("status_update", map[string]string{"status": "Error - Try again"})
				return
			}

			database.DB.Create(&entities.Transcript{
				SessionID: session.ID,
				Role:      "agent",
				Content:   aiResp,
			})

			s.Emit("status_update", map[string]string{"status": "Listening"})
			s.Emit("transcript_update", map[string]string{"role": "agent", "content": aiResp})
			s.Emit("agent_response", map[string]string{"content": aiResp})
		}()
	})

	server.OnEvent("/", "discovery_start", func(s socketio.Conn, data map[string]interface{}) {
		jdText := data["jd_text"].(string)
		go func() {
			s.Emit("discovery_status", map[string]string{"status": "Analyzing JD Content..."})
			skills, err := aiclient.ExtractSkillsFromJD(jdText)
			if err != nil {
				s.Emit("discovery_error", map[string]string{"message": err.Error()})
				return
			}
			s.Emit("discovery_complete", skills)
		}()
	})

	server.OnEvent("/", "terminate_interview", func(s socketio.Conn, data map[string]interface{}) {
		slug := data["session_slug"].(string)
		s.Emit("status_update", map[string]string{"status": "Generating Final Report..."})

		go func() {
			var session entities.InterviewSession
			database.DB.Where("share_url_slug = ?", slug).First(&session)

			var transcripts []entities.Transcript
			database.DB.Where("session_id = ?", session.ID).Order("timestamp asc").Find(&transcripts)

			var history []map[string]interface{}
			for _, t := range transcripts {
				history = append(history, map[string]interface{}{
					"role":    t.Role,
					"content": t.Content,
				})
			}

			var jd entities.JobDescription
			database.DB.First(&jd, "id = ?", session.JDID)

			report, err := aiclient.GenerateInterviewReport(history, jd.RawText, session.ResumeText)
			if err != nil {
				s.Emit("error", map[string]string{"message": "Report generation failed"})
				return
			}

			reportJSON, _ := json.Marshal(report)
			database.DB.Model(&session).Update("final_report", reportJSON)

			s.Emit("report_ready", map[string]interface{}{
				"slug":   slug,
				"report": report,
			})
		}()
	})
}
