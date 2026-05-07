package main

import (
	"devsko-ai-interview/internal/infrastructure/database"
	"devsko-ai-interview/internal/infrastructure/cache"
	"devsko-ai-interview/internal/interfaces/http"
	"devsko-ai-interview/internal/interfaces/socket"
	"log"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/adaptor"
	"github.com/gofiber/fiber/v2/middleware/cors"
	socketio "github.com/googollee/go-socket.io"
)

func main() {
	// 1. Initialize DB & Redis
	database.Connect()
	cache.Connect()

	// 2. Setup Socket.io
	server := socketio.NewServer(nil)
	socket.SetupSocketHandlers(server)

	go func() {
		if err := server.Serve(); err != nil {
			log.Fatalf("socketio listen error: %s\n", err)
		}
	}()
	defer server.Close()

	// 3. Setup Fiber
	app := fiber.New()

	app.Use(cors.New(cors.Config{
		AllowOrigins: "http://localhost:3000",
		AllowHeaders: "Origin, Content-Type, Accept",
	}))

	// API Routes
	api := app.Group("/api")
	api.Post("/jds", http.CreateJD)
	api.Post("/sessions", http.CreateSession)
	api.Get("/sessions/:slug/report", http.GetSessionReport)

	// Socket.io Route
	app.All("/socket.io/*", adaptor.HTTPHandler(server))

	// Start Server
	log.Fatal(app.Listen(":8000"))
}
