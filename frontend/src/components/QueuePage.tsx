import { QueueExperience } from "../QueueExperience";

type QueuePageProps = {
  targetId: number | null;
  reloadSignal: number;
  openItemId?: number | null;
};

export function QueuePage({ targetId, reloadSignal, openItemId }: QueuePageProps) {
  return <QueueExperience collectSignal={reloadSignal} targetId={targetId} openItemId={openItemId} />;
}
