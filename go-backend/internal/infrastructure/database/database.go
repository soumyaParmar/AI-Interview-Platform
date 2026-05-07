package database

import (
	"fmt"
	"log"
	"os"

	"devsko-ai-interview/internal/domain/entities"
	"github.com/joho/godotenv"
	"gorm.io/driver/postgres"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

var DB *gorm.DB

func Connect() {
	if err := godotenv.Load("../../../.env"); err != nil {
		godotenv.Load(".env")
	}

	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "host=localhost user=postgres password=soumya dbname=interview port=5431 sslmode=disable"
	}

	var err error
	if len(dsn) > 10 && dsn[:10] == "postgresql" {
		DB, err = gorm.Open(postgres.Open(dsn), &gorm.Config{})
	} else {
		DB, err = gorm.Open(sqlite.Open("devsko.db"), &gorm.Config{})
	}

	if err != nil {
		log.Fatal("Failed to connect to database: ", err)
	}

	fmt.Println("Database connection successful")

	err = DB.AutoMigrate(&entities.JobDescription{}, &entities.InterviewSession{}, &entities.SkillMap{}, &entities.Transcript{})
	if err != nil {
		log.Fatal("Failed to migrate tables: ", err)
	}
}
