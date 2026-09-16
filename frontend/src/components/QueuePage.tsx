import { QueueExperience } from "../QueueExperience";

type QueuePageProps = {
  targetId: number | null;
  reloadSignal: number;
};

export function QueuePage({ targetId, reloadSignal }: QueuePageProps) {
  return <QueueExperience collectSignal={reloadSignal} targetId={targetId} />;
}
