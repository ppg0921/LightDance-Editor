import React, { useState, useEffect } from "react";
// redux
import { useSelector } from "react-redux";
// actions
import { selectGlobal } from "../../slices/globalSlice";
// my-class
import Controller from "./controller";
// useSelector

/**
 * This is Display component
 *
 * @component
 */

export default function Simulator() {
  const {
    currentStatus,
    currentPos,
    isPlaying,
    controlRecord,
    posRecord,
    timeData,
  } = useSelector(selectGlobal);
  const [controller, setController] = useState(null);

  useEffect(() => {
    const newController = new Controller();
    newController.init();
    setController(newController);
  }, []);

  useEffect(() => {
    if (controller) {
      controller.updateDancersStatus(currentStatus);
    }
  }, [controller, currentStatus]);

  useEffect(() => {
    if (controller) {
      controller.updateDancersPos(currentPos);
    }
  }, [controller, currentPos]);

  useEffect(() => {
    if (controller) {
      if (isPlaying) {
        console.log("Play");
        controller.pixiApp.startTime = performance.now();
        controller.pixiApp.waveSuferTime = timeData.time;
        controller.pixiApp.state = { controlRecord, posRecord };
        controller.pixiApp.state.timeData = { ...timeData };
        controller.tickerF = controller.play.bind(controller);
        controller.pixiApp.ticker.add(controller.tickerF);
      } else {
        console.log("Stop");
        controller.pixiApp.ticker.remove(controller.tickerF);
      }
    }
  }, [isPlaying]);

  return (
    <div
      style={{
        height: "100%",
        width: "100%",
      }}
    >
      <div
        id="pixi"
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
        }}
      >
        <div id="main_stage" />
      </div>
    </div>
  );
}
