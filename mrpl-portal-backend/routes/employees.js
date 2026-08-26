const express = require("express");
const { authenticate } = require("../middleware/auth");
const employeeController = require("../controllers/employeeController");

const router = express.Router();

router.use(authenticate);
router.get("/", employeeController.searchEmployees);

module.exports = router;
