import * as PIXI from "pixi.js";
// utils
import { setItem, getItem } from "../../utils/localStorage";
// redux actions and store
import { posInit, controlInit } from "../../slices/globalSlice";
import store from "../../store";
// components
import Dancer from "./dancer";

import {
  updateFrameByTime,
  interpolationPos,
  fadeStatus,
} from "../../utils/math";
/**
 * Control the dancers (or other light objects)'s status and pos
 * @constructor
 */
class Controller {
  constructor() {
    this.dancers = {};
    this.pixiApp = null;
    this.mainContainer = null;
  }

  /**
   * Initiate localStorage, waveSurferApp, PixiApp, dancers
   */
  init() {
    // initialization by localStorage
    if (!getItem("control")) {
      setItem("control", JSON.stringify(store.getState().load.control));
    }
    if (!getItem("position")) {
      setItem("position", JSON.stringify(store.getState().load.position));
    }
    store.dispatch(controlInit(JSON.parse(getItem("control"))));
    store.dispatch(posInit(JSON.parse(getItem("position"))));

    // initialization for PIXIApp
    this.pixiApp = new PIXI.Application({
      resizeTo: document.getElementById("pixi"),
      backgroundColor: 0x000000,
    });
    this.mainContainer = new PIXI.Container();
    this.mainContainer.sortableChildren = true;
    this.pixiApp.stage.addChild(this.mainContainer);
    document.getElementById("main_stage").appendChild(this.pixiApp.view);

    // initialization for dancers
    const { dancerNames } = store.getState().load;
    dancerNames.forEach((name, idx) => {
      this.dancers[name] = new Dancer(
        idx,
        name,
        this.pixiApp,
        store.getState().load.texture,
        this.mainContainer
      );
    });
  }

  /**
   * update DancersStatus
   * @param {object} currentStatus - all dancers' status
   * ex. { dancer0: { HAT1: 0, ... }}
   */
  updateDancersStatus(currentStatus) {
    if (Object.entries(currentStatus).length === 0)
      throw new Error(
        `[Error] updateDancersStatus, invalid parameter(currentStatus)`
      );
    Object.entries(currentStatus).forEach(([key, value]) => {
      this.dancers[key].setStatus(value);
    });
  }

  /**
   * updateDancersPos
   * @param {*} currentPos
   * ex. { dancer0: { "x": 49.232, "y": 0, "z": 0 }}
   */
  updateDancersPos(currentPos) {
    if (Object.entries(currentPos).length === 0)
      throw new Error(
        `[Error] updateDancersPos, invalid parameter(currentPos)`
      );
    Object.entries(currentPos).forEach(([key, value]) => {
      this.dancers[key].setPos(value);
    });
  }

  play() {
    const time =
      this.pixiApp.waveSuferTime + performance.now() - this.pixiApp.startTime;
    const { state } = this.pixiApp;

    // set timeData.controlFrame and currentStatus
    const newControlFrame = updateFrameByTime(
      state.controlRecord,
      state.timeData.controlFrame,
      time
    );
    state.timeData.controlFrame = newControlFrame;
    // status fade
    if (newControlFrame === state.controlRecord.length - 1) {
      // Can't fade
      state.currentStatus = state.controlRecord[newControlFrame].status;
    } else {
      // do fade
      state.currentStatus = fadeStatus(
        time,
        state.controlRecord[newControlFrame],
        state.controlRecord[newControlFrame + 1]
      );
    }

    // set timeData.posFrame and currentPos
    const newPosFrame = updateFrameByTime(
      state.posRecord,
      state.timeData.posFrame,
      time
    );
    state.timeData.posFrame = newPosFrame;
    // position interpolation
    if (newPosFrame === state.posRecord.length - 1) {
      // can't interpolation
      state.currentPos = state.posRecord[newPosFrame].pos;
    } else {
      // do interpolation
      state.currentPos = interpolationPos(
        time,
        state.posRecord[newPosFrame],
        state.posRecord[newPosFrame + 1]
      );
    }

    // set currentFade
    state.currentFade = state.controlRecord[newControlFrame].fade;

    this.updateDancersStatus(state.currentStatus);
    this.updateDancersPos(state.currentPos);
  }
}

export default Controller;
