const express = require("express");
const { authenticate } = require("../middleware/auth");
const messageController = require("../controllers/messageController");

const router = express.Router();

router.use(authenticate);

router.get("/:employeeId", messageController.getChatHistory);

module.exports = router;
