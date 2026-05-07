package aiclient

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

var OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
var OLLAMA_MODEL = "llama3"

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatRequest struct {
	Model          string    `json:"model"`
	Messages       []Message `json:"messages"`
	ResponseFormat struct {
		Type string `json:"type"`
	} `json:"response_format,omitempty"`
}

type ChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

func GetAIResponse(messages []Message, jsonMode bool) (string, error) {
	reqBody := ChatRequest{
		Model:    OLLAMA_MODEL,
		Messages: messages,
	}
	if jsonMode {
		reqBody.ResponseFormat.Type = "json_object"
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	resp, err := http.Post(OLLAMA_URL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var chatResp ChatResponse
	if err := json.Unmarshal(body, &chatResp); err != nil {
		return "", fmt.Errorf("failed to unmarshal AI response: %v, body: %s", err, string(body))
	}

	if len(chatResp.Choices) > 0 {
		return chatResp.Choices[0].Message.Content, nil
	}

	return "", fmt.Errorf("no choices returned from AI")
}

func ExtractSkillsFromJD(jdText string) (map[string]interface{}, error) {
	prompt := fmt.Sprintf(`
    You are a Recruitment Strategist and JD Architect.
    Analyze the following Job Description (JD) and extract a structured Skill Map.
    
    JD Content:
    %s
    
    Return the response ONLY as a JSON object matching this schema:
    {
        "must_have_tech": ["skill1", ...],
        "nice_to_have_tech": ["skill1", ...],
        "soft_skills": ["skill1", ...],
        "experience_level": "Level",
        "silent_observer_suggestions": ["skill1", ...]
    }
    `, jdText)

	messages := []Message{
		{Role: "system", Content: "You are a professional technical recruiter that outputs ONLY JSON."},
		{Role: "user", Content: prompt},
	}

	resp, err := GetAIResponse(messages, true)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	err = json.Unmarshal([]byte(resp), &result)
	return result, err
}

func GenerateInterviewReport(transcript []map[string]interface{}, jdText, resumeText string) (map[string]interface{}, error) {
	transcriptJSON, _ := json.Marshal(transcript)
	prompt := fmt.Sprintf(`
    JD context: %s
    Resume context: %s
    
    Transcript:
    %s
    
    Perform a multi-tier audit and return the result in the specified JSON schema.
    `, jdText, resumeText, string(transcriptJSON))

	messages := []Message{
		{Role: "system", Content: "You are an Expert Technical Evaluation Analyst & Hiring Strategist."},
		{Role: "user", Content: prompt},
	}

	resp, err := GetAIResponse(messages, true)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	err = json.Unmarshal([]byte(resp), &result)
	return result, err
}
