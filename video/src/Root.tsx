import React from "react";
import { Composition } from "remotion";
import { GravityGapDemo } from "./GravityGapDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="GravityGapDemo"
      component={GravityGapDemo}
      durationInFrames={885}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
