require("dotenv").config();

const path = require("path");
const fs = require("fs");
const http = require("http");
const express = require("express");
const cors = require("cors");
const { Server } = require("socket.io");
const { connectDB } = require("./config/db");
const { registerChatSocket } = require("./socket/chat");
const authRoutes = require("./routes/auth");
const taskRoutes = require("./routes/tasks");
const documentRoutes = require("./routes/documents");
const messageRoutes = require("./routes/messages");
const employeeRoutes = require("./routes/employees");

const PORT = Number(process.env.PORT) || 5000;
const CLIENT_ORIGINS = (process.env.CLIENT_ORIGIN || "http://localhost:3000,http://localhost:3001")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);
const uploadsRoot = path.resolve(process.env.UPLOAD_DIR || path.join(__dirname, "uploads"));

fs.mkdirSync(uploadsRoot, { recursive: true });

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: CLIENT_ORIGINS,
    methods: ["GET", "POST", "PATCH", "DELETE"],
    credentials: true,
  },
});

app.use(
  cors({
    origin: CLIENT_ORIGINS,
    credentials: true,
  })
);
app.use(express.json({ limit: "2mb" }));
app.use(express.urlencoded({ extended: true }));

app.get("/health", (_req, res) => {
  res.json({
    success: true,
    service: "mrpl-portal-backend",
    status: "ok",
    airGapped: true,
  });
});

app.use(authRoutes);
app.use("/api/auth", authRoutes);
app.use("/api/tasks", taskRoutes);
app.use("/api/documents", documentRoutes);
app.use("/api/messages", messageRoutes);
app.use("/api/employees", employeeRoutes);

app.use((req, res) => {
  res.status(404).json({ success: false, message: `Route not found: ${req.method} ${req.originalUrl}` });
});

app.use((err, _req, res, _next) => {
  if (err.code === "LIMIT_FILE_SIZE") {
    return res.status(400).json({ success: false, message: "File exceeds the 25MB upload limit." });
  }

  console.error("[api]", err);
  return res.status(err.status || 500).json({
    success: false,
    message: err.message || "Internal server error.",
  });
});

registerChatSocket(io);

async function start() {
  await connectDB();

  server.listen(PORT, () => {
    console.log(`[server] MRPL portal API listening on http://localhost:${PORT}`);
    console.log(`[server] CORS origins: ${CLIENT_ORIGINS.join(", ")}`);
    console.log(`[server] Uploads directory: ${uploadsRoot}`);
  });
}

start().catch((error) => {
  console.error("[server] Failed to start:", error);
  process.exit(1);
});
