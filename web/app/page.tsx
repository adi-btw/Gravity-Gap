import type { Metadata } from "next";
import { getStoryData } from "@/components/story/data";
import { StoryPage } from "@/components/story/StoryPage";

export const metadata: Metadata = {
  title: "Gravity Gap · An evidence report on fire between orbit and Earth",
  description:
    "NASA's fire tests ran in orbit or on Earth, never at Moon or Mars gravity. Gravity Gap carries the evidence across that gap and refuses to give a number where there is none.",
};

/** The story page: a scroll-driven evidence report that leads into the tool. Data is read at build time. */
export default function Home() {
  return <StoryPage data={getStoryData()} />;
}
