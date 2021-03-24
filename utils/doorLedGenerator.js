// Usage
// node ./utils/doorLedGenerator doorName

const { exit } = require("process");
const fs = require("fs"),
  PNG = require("pngjs").PNG;
const DOOR_L_PATH = "./asset/LEDParts/led_l_door";
const DOOR_R_PATH = "./asset/LEDParts/led_r_door";
const BL_PATH = `${DOOR_L_PATH}/bl_door.png`;

function parse(door, WIDTH, HEIGHT, type, color, pos, dir) {
  Object.entries(color).map(([name, val]) => {
    if (name[name.length - 1] === type) {
      const [l, u, r, d] = pos[name];
      if (dir[name] === "horizontal") {
        // left
        for (let i = u; i < d; i += 1) {
          // loop the color
          let j = l;
          for (let idx = 0; idx < color[name].length; idx += 2) {
            const len = color[name][idx];
            const c = color[name][idx + 1];
            const r_limit = j + len < r ? j + len : r;
            for (; j < r_limit; j += 1) {
              const b = c % 256;
              const g = (c >> 8) % 256;
              const r = (c >> 16) % 256;
              const png_idx = (WIDTH * i + j) << 2;
              door[png_idx] = r;
              door[png_idx + 1] = g;
              door[png_idx + 2] = b;
            }
          }
        }
      } else {
        // vertical
        for (let idx = 0; idx < color[name].length; idx += 2) {
          const len = color[name][idx];
          const c = color[name][idx + 1];
          let i = u;
          const d_limit = i + len < d ? i + len : d;
          for (; i < d_limit; i += 1) {
            for (let j = l; j < r; j += 1) {
              const b = c % 256;
              const g = (c >> 8) % 256;
              const r = (c >> 16) % 256;
              const png_idx = (WIDTH * i + j) << 2;
              door[png_idx] = r;
              door[png_idx + 1] = g;
              door[png_idx + 2] = b;
            }
          }
        }
      }
    }
  });
}

function generate(outputName) {
  // door_L
  fs.createReadStream(BL_PATH)
    .pipe(
      new PNG({
        colorType: 6,
      })
    )
    .on("parsed", function () {
      parse(this.data, this.width, this.height, "L", color, pos, dir);
      this.pack().pipe(
        fs.createWriteStream(`${DOOR_L_PATH}/${outputName}.png`)
      );
    });

  // door_R
  fs.createReadStream(BL_PATH)
    .pipe(
      new PNG({
        colorType: 6,
      })
    )
    .on("parsed", function () {
      parse(this.data, this.width, this.height, "R", color, pos, dir);
      this.pack().pipe(
        fs.createWriteStream(`${DOOR_R_PATH}/${outputName}.png`)
      );
    });
}

// Read Argument
const args = process.argv; // 0: node, 1: controlTransform.js
if (args.length < 3) {
  console.error(`[Error] Invalid Arguments !!!`);
  exit();
}
const outputName = args[2];

// color config
// <name> : [長度, 顏色, 長度, 顏色 ...]
const color = {
  TOP_L: [150, 0x0000ff], // 左到右，共 150 顆
  MID_L: [30, 0x00ff00], // 左到右，共 30 顆
  BTM_L: [100, 0xff0000], // 左到右，共 100 顆
  PILLAR_L: [120, 0xffffff], // 上到下，共 120 顆
  TOP_R: [150, 0x0000ff], // 右到左，共 150 顆
  MID_R: [30, 0x00ff00], // 右到左，共 30 顆
  BTM_R: [100, 0xff0000], // 右到左，共 100 顆
  PILLAR_R: [120, 0xffffff], // 上到下，共 120 顆
};

// position config
// <name> : [左、上、右、下]
const pos = {
  TOP_L: [0, 0, 150, 30],
  MID_L: [80, 30, 110, 60],
  BTM_L: [50, 60, 150, 90],
  PILLAR_L: [80, 90, 110, 210],
  TOP_R: [0, 0, 150, 30],
  MID_R: [40, 30, 70, 60],
  BTM_R: [0, 60, 100, 90],
  PILLAR_R: [40, 90, 70, 210],
};

// direction config
const dir = {
  TOP_L: "horizontal",
  MID_L: "horizontal",
  BTM_L: "horizontal",
  PILLAR_L: "vertical",
  TOP_R: "horizontal",
  MID_R: "horizontal",
  BTM_R: "horizontal",
  PILLAR_R: "vertical",
};

generate(outputName, color, pos, dir);
