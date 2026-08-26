const express = require("express");
const { authenticate, requireManager } = require("../middleware/auth");
const taskController = require("../controllers/taskController");

const router = express.Router();

router.use(authenticate);

router.get("/", taskController.listMyTasks);
router.post("/", requireManager, taskController.createTask);
router.patch("/:id/status", taskController.updateTaskStatus);

module.exports = router;
