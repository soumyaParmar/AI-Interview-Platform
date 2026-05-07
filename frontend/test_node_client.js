const { io } = require("socket.io-client");

const socket = io("http://localhost:8000", {
  reconnectionAttempts: 5,
  transports: ['websocket', 'polling']
});

socket.on("connect", () => {
  console.log("Connected to backend from Node!");
  socket.emit("join_interview", { session_slug: "test-session-123" });
});

socket.on("system_message", (data) => {
  console.log("System:", data);
  socket.emit("user_answer", { session_slug: "test-session-123", text: "Hello node!" });
});

socket.on("transcript_update", (data) => {
  console.log("Transcript:", data);
});

setTimeout(() => {
  socket.disconnect();
  process.exit(0);
}, 3000);
