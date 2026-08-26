const jwt = require("jsonwebtoken");
const User = require("../models/User");
const { sendError } = require("../utils/http");

async function authenticate(req, res, next) {
  try {
    const header = req.headers.authorization || "";
    const token = header.startsWith("Bearer ") ? header.slice(7) : null;

    if (!token) {
      return sendError(res, 401, "Authentication token is required.");
    }

    const payload = jwt.verify(token, process.env.JWT_SECRET);
    const user = await User.findById(payload.sub);

    if (!user) {
      return sendError(res, 401, "User no longer exists.");
    }

    req.user = user;
    next();
  } catch (error) {
    if (error.name === "TokenExpiredError") {
      return sendError(res, 401, "Token has expired. Please log in again.");
    }
    return sendError(res, 401, "Invalid authentication token.");
  }
}

function requireManager(req, res, next) {
  if (req.user?.role !== "Manager") {
    return sendError(res, 403, "Only managers can perform this action.");
  }
  next();
}

function signToken(user) {
  return jwt.sign(
    {
      sub: user._id.toString(),
      employeeId: user.employeeId,
      role: user.role,
    },
    process.env.JWT_SECRET,
    { expiresIn: process.env.JWT_EXPIRES_IN || "8h" }
  );
}

module.exports = { authenticate, requireManager, signToken };
