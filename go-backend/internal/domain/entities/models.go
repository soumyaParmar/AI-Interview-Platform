package entities

import (
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

type JobDescription struct {
	ID        string    `gorm:"primaryKey;type:varchar(255)"`
	RawText   string    `gorm:"type:text;not null"`
	CreatedAt time.Time `gorm:"default:CURRENT_TIMESTAMP"`
}

func (jd *JobDescription) BeforeCreate(tx *gorm.DB) (err error) {
	jd.ID = uuid.New().String()
	return
}

type InterviewSession struct {
	ID            string    `gorm:"primaryKey;type:varchar(255)"`
	JDID          string    `gorm:"type:varchar(255);not null"`
	ShareURLSlug  string    `gorm:"type:varchar(255);unique;not null"`
	CandidateName string    `gorm:"type:varchar(255)"`
	ResumeText    string    `gorm:"type:text"`
	FinalReport   []byte    `gorm:"type:jsonb"`
	CreatedAt     time.Time `gorm:"default:CURRENT_TIMESTAMP"`
}

func (s *InterviewSession) BeforeCreate(tx *gorm.DB) (err error) {
	s.ID = uuid.New().String()
	return
}

type SkillMap struct {
	ID               string  `gorm:"primaryKey;type:varchar(255)"`
	SessionID        string  `gorm:"type:varchar(255);not null"`
	SkillName        string  `gorm:"type:varchar(100)"`
	ImportanceWeight float64 `gorm:"type:float"`
	IsCovered        bool    `gorm:"default:false"`
	Score            int     `gorm:"default:0"`
}

func (sm *SkillMap) BeforeCreate(tx *gorm.DB) (err error) {
	sm.ID = uuid.New().String()
	return
}

type Transcript struct {
	ID             string    `gorm:"primaryKey;type:varchar(255)"`
	SessionID      string    `gorm:"type:varchar(255);not null"`
	Role           string    `gorm:"type:varchar(20)"`
	Content        string    `gorm:"type:text"`
	StatusMetadata []byte    `gorm:"type:jsonb"`
	Timestamp      time.Time `gorm:"default:CURRENT_TIMESTAMP"`
}

func (t *Transcript) BeforeCreate(tx *gorm.DB) (err error) {
	t.ID = uuid.New().String()
	return
}
