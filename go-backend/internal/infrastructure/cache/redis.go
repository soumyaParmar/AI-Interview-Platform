package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/redis/go-redis/v9"
)

var Client *redis.Client
var Ctx = context.Background()

func Connect() {
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379/0"
	}

	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Fatal("Failed to parse Redis URL: ", err)
	}

	Client = redis.NewClient(opt)

	if _, err := Client.Ping(Ctx).Result(); err != nil {
		log.Fatal("Failed to connect to Redis: ", err)
	}

	fmt.Println("Redis connection successful")
}

func SetSessionState(sessionID string, stateData map[string]interface{}) error {
	data, err := json.Marshal(stateData)
	if err != nil {
		return err
	}
	return Client.Set(Ctx, fmt.Sprintf("session:%s:state", sessionID), data, 0).Err()
}

func GetSessionState(sessionID string) (map[string]interface{}, error) {
	data, err := Client.Get(Ctx, fmt.Sprintf("session:%s:state", sessionID)).Result()
	if err != nil {
		return nil, err
	}

	var state map[string]interface{}
	if err := json.Unmarshal([]byte(data), &state); err != nil {
		return nil, err
	}
	return state, nil
}
