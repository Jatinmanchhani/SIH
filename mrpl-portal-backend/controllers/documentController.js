const path = require("path");
const fs = require("fs");
const Document = require("../models/Document");
const { asyncHandler, sendError, sendSuccess } = require("../utils/http");

const DOCUMENT_TYPES = ["Manual", "SOP", "Drawing", "Other"];

function getUploadsRoot() {
  return path.resolve(process.env.UPLOAD_DIR || path.join(__dirname, "..", "uploads"));
}

function isPathInsideUploads(filePath) {
  const uploadsRoot = getUploadsRoot();
  const resolved = path.resolve(filePath);
  return resolved === uploadsRoot || resolved.startsWith(uploadsRoot + path.sep);
}

exports.uploadDocument = asyncHandler(async (req, res) => {
  if (!req.file) {
    return sendError(res, 400, "A file is required. Use the 'file' form field.");
  }

  const type = DOCUMENT_TYPES.includes(req.body?.type) ? req.body.type : "Other";
  const pages = Number.parseInt(req.body?.pages, 10);

  const document = await Document.create({
    name: (req.body?.name || req.file.originalname).trim(),
    type,
    filePath: req.file.path,
    originalName: req.file.originalname,
    mimeType: req.file.mimetype,
    pages: Number.isFinite(pages) && pages >= 0 ? pages : 0,
    uploadedBy: req.user._id,
  });

  const populated = await Document.findById(document._id).populate(
    "uploadedBy",
    "employeeId name role"
  );

  return sendSuccess(res, { document: populated }, 201);
});

exports.listDocuments = asyncHandler(async (req, res) => {
  const documents = await Document.find()
    .populate("uploadedBy", "employeeId name role")
    .sort({ createdAt: -1 });

  return sendSuccess(res, { documents });
});

exports.downloadDocument = asyncHandler(async (req, res) => {
  const document = await Document.findById(req.params.id);
  if (!document) {
    return sendError(res, 404, "Document not found.");
  }

  if (!isPathInsideUploads(document.filePath)) {
    return sendError(res, 400, "Stored file path is outside the uploads directory.");
  }

  if (!fs.existsSync(document.filePath)) {
    return sendError(res, 404, "File is missing from the local uploads directory.");
  }

  return res.download(document.filePath, document.originalName || document.name);
});

exports.deleteDocument = asyncHandler(async (req, res) => {
  const document = await Document.findById(req.params.id);
  if (!document) {
    return sendError(res, 404, "Document not found.");
  }

  const ownerId = document.uploadedBy.toString();
  const isOwner = ownerId === req.user._id.toString();
  const isManager = req.user.role === "Manager";

  if (!isOwner && !isManager) {
    return sendError(res, 403, "You can only delete documents you uploaded.");
  }

  if (isPathInsideUploads(document.filePath) && fs.existsSync(document.filePath)) {
    fs.unlinkSync(document.filePath);
  }

  await document.deleteOne();

  return sendSuccess(res, { message: "Document deleted." });
});
