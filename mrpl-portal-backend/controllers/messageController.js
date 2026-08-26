const User = require("../models/User");
const Message = require("../models/Message");
const { asyncHandler, sendError, sendSuccess } = require("../utils/http");

exports.getChatHistory = asyncHandler(async (req, res) => {
  const targetEmployeeId = req.params.employeeId?.trim();

  if (!targetEmployeeId) {
    return sendError(res, 400, "Target employeeId is required.");
  }

  const target = await User.findOne({ employeeId: targetEmployeeId });
  if (!target) {
    return sendError(res, 404, `No employee found with ID ${targetEmployeeId}.`);
  }

  const messages = await Message.find({
    $or: [
      { sender: req.user._id, receiver: target._id },
      { sender: target._id, receiver: req.user._id },
    ],
  })
    .populate("sender", "employeeId name role")
    .populate("receiver", "employeeId name role")
    .sort({ timestamp: 1 });

  return sendSuccess(res, { messages });
});
