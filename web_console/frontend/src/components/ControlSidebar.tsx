import type { NavigationGoal, NavigationTaskState } from "../types";
import { formatNumber, formatNullable } from "../utils/format";

interface ControlSidebarProps {
  navigation: NavigationTaskState | null;
  selectedGoal: NavigationGoal | null;
  canSendGoal: boolean;
  canSetInitialPose: boolean;
  onSetInitialPose: () => void;
  onSendGoal: () => void;
  onCancelGoal: () => void;
  lastError: string | null;
  lastSuccess: string | null;
}

export function ControlSidebar({
  navigation,
  selectedGoal,
  canSendGoal,
  canSetInitialPose,
  onSetInitialPose,
  onSendGoal,
  onCancelGoal,
  lastError,
  lastSuccess,
}: ControlSidebarProps) {
  return (
    <aside className="sidebar">
      <section className="panel">
        <h2>任务状态</h2>
        <TaskStateChip state={navigation?.state ?? "idle"} />
        <p className="panel-message">{formatNullable(navigation?.message)}</p>
        <StatusMini label="action server" value={navigation?.action_server_ready ? "ready" : "unavailable"} />
        <StatusMini
          label="distance remaining"
          value={formatNullable(
            navigation?.feedback?.distance_remaining === undefined
              ? null
              : `${formatNumber(Number(navigation.feedback.distance_remaining), 2)} m`,
          )}
        />
      </section>

      <section className="panel">
        <h2>当前选点</h2>
        <StatusMini label="x" value={formatNumber(selectedGoal?.x, 2)} />
        <StatusMini label="y" value={formatNumber(selectedGoal?.y, 2)} />
        <StatusMini label="yaw" value={formatNumber(selectedGoal?.yaw, 2)} />
        <div className="button-group">
          <button className="secondary-button" disabled={!selectedGoal || !canSetInitialPose} onClick={onSetInitialPose}>
            设置初始位姿
          </button>
          <button className="primary-button" disabled={!selectedGoal || !canSendGoal} onClick={onSendGoal}>
            发送导航
          </button>
          <button className="danger-button" onClick={onCancelGoal}>
            停止导航
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>最近提示</h2>
        <p className={`notice ${lastError ? "notice-error" : ""}`}>{formatNullable(lastError, "暂无错误")}</p>
        <p className={`notice ${lastSuccess ? "notice-success" : ""}`}>{formatNullable(lastSuccess, "暂无成功提示")}</p>
      </section>
    </aside>
  );
}

function TaskStateChip({ state }: { state: string }) {
  return <div className={`task-chip task-chip-${state}`}>{state}</div>;
}

function StatusMini({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-row">
      <span className="status-label">{label}</span>
      <span className="status-value">{value}</span>
    </div>
  );
}
