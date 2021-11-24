const { exit } = require("process");
const fs = require("fs"),
  const = require("../data/led.json");

function initilize(ledToAdd) {
  const led = [];
  led;
}

const LED_JSON_PATH = "./data/led.json";

// Read Argument
const args = process.argv; // 0: node, 1: controlTransform.js
if (args.length < 3) {
  console.error(`[Error] Invalid Arguments !!!`);
  exit();
}
const ledToAdd = args[2];

add;
