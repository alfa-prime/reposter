import { QueueExperience } from "../QueueExperience";

type QueuePageProps = {
  targetId: number | null;
};

export function QueuePage({ targetId }: QueuePageProps) {
  return <QueueExperience targetId={targetId} />;
}
