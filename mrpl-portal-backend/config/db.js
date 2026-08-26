const mongoose = require("mongoose");

async function connectDB() {
  const uri = process.env.MONGODB_URI || "mongodb://localhost:27017/mrpl-portal";

  mongoose.set("strictQuery", true);

  await mongoose.connect(uri);
  console.log(`[db] Connected to MongoDB at ${uri}`);
}

module.exports = { connectDB };
