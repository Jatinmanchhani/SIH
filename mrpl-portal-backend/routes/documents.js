const express = require("express");
const { authenticate } = require("../middleware/auth");
const { upload } = require("../middleware/upload");
const documentController = require("../controllers/documentController");

const router = express.Router();

router.use(authenticate);

router.post("/upload", upload.single("file"), documentController.uploadDocument);
router.get("/", documentController.listDocuments);
router.get("/download/:id", documentController.downloadDocument);
router.delete("/:id", documentController.deleteDocument);

module.exports = router;
