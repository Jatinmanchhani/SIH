const jwt = require("jsonwebtoken");
const User = require("../models/User");
const Message = require("../models/Message");

function registerChatSocket(io) {
  const socketToEmployee = new Map();
  const employeeToSocket = new Map();

  io.use(async (socket, next) => {
    try {
      const employeeId =
        socket.handshake.auth?.employeeId || socket.handshake.query?.employeeId;
      const token = socket.handshake.auth?.token || socket.handshake.query?.token;

      if (!employeeId) {
        return next(new Error("employeeId is required to connect."));
      }

      if (token) {
        const payload = jwt.verify(token, process.env.JWT_SECRET);
        if (payload.employeeId !== employeeId) {
          return next(new Error("Socket employeeId does not match token."));
        }
      }

      const user = await User.findOne({ employeeId });
      if (!user) {
        return next(new Error("Unknown employeeId."));
      }

      socket.employeeId = user.employeeId;
      socket.userId = user._id.toString();
      next();
    } catch {
      next(new Error("Socket authentication failed."));
    }
  });

  io.on("connection", (socket) => {
    const { employeeId } = socket;

    socketToEmployee.set(socket.id, employeeId);
    employeeToSocket.set(employeeId, socket.id);
    socket.join(employeeId);

    console.log(`[socket] ${employeeId} connected (${socket.id})`);

    socket.emit("connected", { employeeId, socketId: socket.id });

    socket.on("send_message", async (payload = {}, ack) => {
      try {
        const targetEmployeeId = payload.targetEmployeeId?.trim();
        const content = payload.content?.trim();

        if (!targetEmployeeId || !content) {
          const error = { success: false, message: "targetEmployeeId and content are required." };
          if (typeof ack === "function") ack(error);
          socket.emit("message_error", error);
          return;
        }

        const [sender, receiver] = await Promise.all([
          User.findOne({ employeeId }),
          User.findOne({ employeeId: targetEmployeeId }),
        ]);

        if (!receiver) {
          const error = { success: false, message: `No employee found with ID ${targetEmployeeId}.` };
          if (typeof ack === "function") ack(error);
          socket.emit("message_error", error);
          return;
        }

        const message = await Message.create({
          sender: sender._id,
          receiver: receiver._id,
          content,
          timestamp: new Date(),
        });

        const dto = {
          id: message._id,
          content: message.content,
          timestamp: message.timestamp,
          sender: {
            id: sender._id,
            employeeId: sender.employeeId,
            name: sender.name,
            role: sender.role,
          },
          receiver: {
            id: receiver._id,
            employeeId: receiver.employeeId,
            name: receiver.name,
            role: receiver.role,
          },
        };

        const targetSocketId = employeeToSocket.get(targetEmployeeId);
        if (targetSocketId) {
          io.to(targetSocketId).emit("receive_message", dto);
        }

        socket.emit("message_sent", dto);
        if (typeof ack === "function") ack({ success: true, message: dto });
      } catch (error) {
        const failure = { success: false, message: error.message || "Failed to send message." };
        if (typeof ack === "function") ack(failure);
        socket.emit("message_error", failure);
      }
    });

    socket.on("disconnect", () => {
      socketToEmployee.delete(socket.id);
      if (employeeToSocket.get(employeeId) === socket.id) {
        employeeToSocket.delete(employeeId);
      }
      console.log(`[socket] ${employeeId} disconnected (${socket.id})`);
    });
  });

  return { socketToEmployee, employeeToSocket };
}

module.exports = { registerChatSocket };
