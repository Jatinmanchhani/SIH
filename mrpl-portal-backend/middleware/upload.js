const path = require("path");
const fs = require("fs");
const multer = require("multer");

const uploadsRoot = path.resolve(process.env.UPLOAD_DIR || path.join(__dirname, "..", "uploads"));

fs.mkdirSync(uploadsRoot, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, uploadsRoot);
  },
  filename: (_req, file, cb) => {
    const safeOriginal = path
      .basename(file.originalname)
      .replace(/[^a-zA-Z0-9._-]/g, "_");
    cb(null, `${Date.now()}-${safeOriginal}`);
  },
});

const upload = multer({
  storage,
  limits: {
    fileSize: 25 * 1024 * 1024,
  },
});

module.exports = { upload, uploadsRoot };
