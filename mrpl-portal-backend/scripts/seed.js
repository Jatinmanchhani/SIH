require("dotenv").config();

const mongoose = require("mongoose");
const bcrypt = require("bcryptjs");
const User = require("../models/User");

const FIRST_NAMES = [
  "Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Meera", "Arjun", "Kavya",
  "Nikhil", "Sneha", "Rahul", "Isha", "Sanjay", "Divya", "Karan", "Nisha",
  "Amit", "Pooja", "Deepak", "Neha", "Suresh", "Anjali", "Manoj", "Ritu",
  "Harish", "Shreya", "Gaurav", "Aditi", "Rajesh", "Swati",
];

const LAST_NAMES = [
  "Sharma", "Patel", "Nair", "Reddy", "Iyer", "Khan", "Das", "Menon",
  "Gupta", "Joshi", "Kulkarni", "Singh", "Pillai", "Rao", "Mehta", "Bhat",
];

function buildName(index) {
  const first = FIRST_NAMES[index % FIRST_NAMES.length];
  const last = LAST_NAMES[Math.floor(index / FIRST_NAMES.length) % LAST_NAMES.length];
  return `${first} ${last}`;
}

async function seed() {
  const uri = process.env.MONGODB_URI || "mongodb://localhost:27017/mrpl-portal";

  await mongoose.connect(uri);
  console.log(`[seed] Connected to ${uri}`);

  await User.deleteMany({});
  console.log("[seed] Cleared existing users");

  const hashedPassword = await bcrypt.hash("Password@123", 10);
  const users = [];

  for (let i = 0; i < 200; i += 1) {
    const employeeNumber = 1000 + i;
    const employeeId = `MRPL-${employeeNumber}`;
    const role = i < 10 ? "Manager" : "Employee";

    users.push({
      employeeId,
      name: buildName(i),
      role,
      password: hashedPassword,
    });
  }

  await User.insertMany(users);

  const managers = users.filter((user) => user.role === "Manager").map((user) => user.employeeId);
  console.log(`[seed] Inserted ${users.length} employees (MRPL-1000 to MRPL-1199)`);
  console.log(`[seed] Managers (${managers.length}): ${managers.join(", ")}`);
  console.log("[seed] Default password for all users: Password@123");

  await mongoose.disconnect();
  console.log("[seed] Done");
}

seed().catch((error) => {
  console.error("[seed] Failed:", error);
  process.exit(1);
});
