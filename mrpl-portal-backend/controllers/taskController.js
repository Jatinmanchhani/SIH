const Task = require("../models/Task");
const User = require("../models/User");
const { asyncHandler, sendError, sendSuccess } = require("../utils/http");

const ALLOWED_STATUSES = ["Pending", "In Progress", "Completed"];

exports.listMyTasks = asyncHandler(async (req, res) => {
  const userId = req.user._id;
  const employeeId = req.user.employeeId;
  const role = req.user.role;
  
  // Check if the user is a Manager (either by role field, or by ID number < MRPL-1010)
  const numericId = parseInt(employeeId.replace("MRPL-", ""));
  const isManager = role === "Manager" || numericId <= 1009;

  let query = {};
  if (isManager) {
    // If manager, find tasks they created
    query = { createdBy: userId };
  } else {
    // If employee, find tasks assigned to them using their database _id
    query = { assignedTo: userId };
  }

  // Fetch tasks and populate both the creator and assignee details
  const tasks = await Task.find(query)
    .populate("assignedTo", "employeeId name role")
    .populate("createdBy", "employeeId name role")
    .sort({ createdAt: -1 });

  return sendSuccess(res, { tasks });
});

exports.createTask = asyncHandler(async (req, res) => {
  const { title, employeeId, status } = req.body || {};

  if (!title || !employeeId) {
    return sendError(res, 400, "title and employeeId are required.");
  }

  const assignee = await User.findOne({ employeeId: employeeId.trim() });
  if (!assignee) {
    return sendError(res, 404, `No employee found with ID ${employeeId}.`);
  }

  const initialStatus = ALLOWED_STATUSES.includes(status) ? status : "Pending";

  const task = await Task.create({
    title: title.trim(),
    status: initialStatus,
    assignedTo: assignee._id,
    createdBy: req.user._id,
  });

  const populated = await Task.findById(task._id)
    .populate("assignedTo", "employeeId name role")
    .populate("createdBy", "employeeId name role");

  return sendSuccess(res, { task: populated }, 201);
});

exports.updateTaskStatus = asyncHandler(async (req, res) => {
  const { id } = req.params;
  const nextStatus = req.body?.status || "Completed";

  if (!ALLOWED_STATUSES.includes(nextStatus)) {
    return sendError(res, 400, `status must be one of: ${ALLOWED_STATUSES.join(", ")}.`);
  }

  const task = await Task.findById(id);
  if (!task) {
    return sendError(res, 404, "Task not found.");
  }

  const isAssignee = task.assignedTo.toString() === req.user._id.toString();
  const isManager = req.user.role === "Manager";

  if (!isAssignee && !isManager) {
    return sendError(res, 403, "You can only update tasks assigned to you.");
  }

  if (isAssignee && !isManager && nextStatus !== "Completed") {
    return sendError(res, 400, "Employees may only mark a task as Completed.");
  }

  task.status = nextStatus;
  await task.save();

  const populated = await Task.findById(task._id)
    .populate("assignedTo", "employeeId name role")
    .populate("createdBy", "employeeId name role");

  return sendSuccess(res, { task: populated });
});