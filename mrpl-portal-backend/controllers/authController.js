const crypto = require("crypto");
const bcrypt = require("bcryptjs");
const User = require("../models/User");
const { asyncHandler, sendError, sendSuccess } = require("../utils/http");
const { signToken } = require("../middleware/auth");

function hashResetToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

exports.me = asyncHandler(async (req, res) => {
  return sendSuccess(res, {
    employee: {
      id: req.user._id,
      employeeId: req.user.employeeId,
      name: req.user.name,
      role: req.user.role,
    },
  });
});

exports.login = asyncHandler(async (req, res) => {
  const { employeeId, password } = req.body || {};

  if (!employeeId || !password) {
    return sendError(res, 400, "employeeId and password are required.");
  }

  const user = await User.findOne({ employeeId: employeeId.trim() }).select("+password");
  if (!user) {
    return sendError(res, 401, "Invalid employee ID or password.");
  }

  const matches = await bcrypt.compare(password, user.password);
  if (!matches) {
    return sendError(res, 401, "Invalid employee ID or password.");
  }

  const token = signToken(user);

  return sendSuccess(res, {
    token,
    employee: {
      id: user._id,
      employeeId: user.employeeId,
      name: user.name,
      role: user.role,
    },
  });
});

exports.forgotPassword = asyncHandler(async (req, res) => {
  const { employeeId } = req.body || {};

  if (!employeeId) {
    return sendError(res, 400, "employeeId is required.");
  }

  const user = await User.findOne({ employeeId: employeeId.trim() });

  // Always return the same message so employee IDs are not enumerable.
  if (!user) {
    return sendSuccess(res, {
      message: "If that employee ID exists, a reset link was issued to the operations console.",
    });
  }

  const rawToken = crypto.randomBytes(32).toString("hex");
  user.passwordResetToken = hashResetToken(rawToken);
  user.passwordResetExpires = new Date(Date.now() + 30 * 60 * 1000);
  await user.save();

  const frontendUrl = process.env.FRONTEND_URL || "http://localhost:3000";
  const resetLink = `${frontendUrl}/reset-password?employeeId=${encodeURIComponent(
    user.employeeId
  )}&token=${rawToken}`;

  console.log("============================================================");
  console.log("[SIMULATED EMAIL] Air-gapped password reset (not sent)");
  console.log(`To: ${user.employeeId} <${user.name}>`);
  console.log("Subject: MRPL Portal password reset");
  console.log(`Reset link: ${resetLink}`);
  console.log("This link expires in 30 minutes.");
  console.log("============================================================");

  return sendSuccess(res, {
    message: "If that employee ID exists, a reset link was issued to the operations console.",
  });
});

exports.resetPassword = asyncHandler(async (req, res) => {
  const { employeeId, token, newPassword } = req.body || {};

  if (!employeeId || !token || !newPassword) {
    return sendError(res, 400, "employeeId, token, and newPassword are required.");
  }

  if (newPassword.length < 8 || !/[A-Z]/.test(newPassword)) {
    return sendError(
      res,
      400,
      "Password must be at least 8 characters and contain an uppercase letter."
    );
  }

  const user = await User.findOne({
    employeeId: employeeId.trim(),
    passwordResetToken: hashResetToken(token),
    passwordResetExpires: { $gt: new Date() },
  }).select("+password +passwordResetToken +passwordResetExpires");

  if (!user) {
    return sendError(res, 400, "Reset token is invalid or has expired.");
  }

  user.password = await bcrypt.hash(newPassword, 10);
  user.passwordResetToken = undefined;
  user.passwordResetExpires = undefined;
  await user.save();

  return sendSuccess(res, { message: "Password has been reset. You can now log in." });
});
