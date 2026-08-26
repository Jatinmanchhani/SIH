const User = require("../models/User");
const { asyncHandler, sendSuccess } = require("../utils/http");

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

exports.searchEmployees = asyncHandler(async (req, res) => {
  const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
  const filter = {};

  if (q) {
    const safe = escapeRegex(q);
    filter.$or = [
      { employeeId: { $regex: safe, $options: "i" } },
      { name: { $regex: safe, $options: "i" } },
    ];
  }

  const employees = await User.find(filter)
    .select("employeeId name role")
    .sort({ employeeId: 1 })
    .limit(25);

  return sendSuccess(res, { employees });
});
