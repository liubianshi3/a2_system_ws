import { useEffect, useState } from "react";

import { cancelNavigationGoal, fetchHealth, fetchSnapshot, sendInitialPose, sendNavigationGoal } from "./api";
import { ControlSidebar } from "./components/ControlSidebar";
import { MapCanvas } from "./components/MapCanvas";
import { StatusSidebar } from "./components/StatusSidebar";
import { useBackendSocket } from "./hooks/useBackendSocket";
import type { BackendEvent, DashboardSnapshot, NavigationGoal } from "./types";

function createEmptySnapshot(): DashboardSnapshot {
  return {
    map: {
      loaded: false,
      frame_id: null,
      width: 0,
      height: 0,
      resolution: 0,
      origin: { x: 0, y: 0, yaw: 0 },
      stamp: null,
      data: [],
    },
    pose: {
      available: false,
      source: "amcl_pose",
      frame_id: null,
      stamp: null,
      x: null,
      y: null,
      yaw: null,
      stale: true,
    },
    status: {
      system_ready: null,
      localization_ok: null,
      real_report: { raw: null, mode: null, state: null, ready: null, reason: null, fields: {} },
      lidar_status: { raw: null, mode: null, state: null, ready: null, reason: null, fields: {} },
      localization_status: { raw: null, mode: null, state: null, ready: null, reason: null, fields: {} },
      map_manager_status: { raw: null, mode: null, state: null, ready: null, reason: null, fields: {} },
      sdk_status: { raw: null, mode: null, state: null, ready: null, reason: null, fields: {} },
      active_map: null,
      velocity_linear_x: null,
      velocity_angular_z: null,
      raw_state: null,
    },
    navigation: {
      state: "idle",
      message: null,
      action_server_ready: false,
      goal: null,
      feedback: {},
      updated_at: null,
    },
    health: {
      backend_ok: false,
      ros_connected: false,
      ros_thread_alive: false,
      websocket_clients: 0,
      action_server_ready: false,
      map_received: false,
      pose_received: false,
      last_map_update: null,
      last_pose_update: null,
      last_error: null,
    },
  };
}

export default function App() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(createEmptySnapshot());
  const [selectedGoal, setSelectedGoal] = useState<NavigationGoal | null>(null);
  const [backendConnected, setBackendConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSnapshot()
      .then((data) => {
        if (cancelled) {
          return;
        }
        setSnapshot(data);
        setBackendConnected(true);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLastError(error instanceof Error ? error.message : "无法获取初始快照");
        setBackendConnected(false);
      });

    fetchHealth()
      .then((health) => {
        if (cancelled) {
          return;
        }
        setSnapshot((current) => ({ ...current, health }));
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  const { connected: websocketConnected, lastError: websocketError } = useBackendSocket({
    onEvent: (event: BackendEvent<unknown>) => {
      setBackendConnected(true);
      if (event.type === "snapshot") {
        setSnapshot(event.payload as DashboardSnapshot);
        return;
      }
      if (event.type === "map") {
        setSnapshot((current) => ({ ...current, map: event.payload as DashboardSnapshot["map"] }));
        return;
      }
      if (event.type === "pose") {
        setSnapshot((current) => ({ ...current, pose: event.payload as DashboardSnapshot["pose"] }));
        return;
      }
      if (event.type === "status") {
        setSnapshot((current) => ({ ...current, status: event.payload as DashboardSnapshot["status"] }));
        return;
      }
      if (event.type === "navigation") {
        setSnapshot((current) => ({ ...current, navigation: event.payload as DashboardSnapshot["navigation"] }));
        return;
      }
      if (event.type === "health") {
        setSnapshot((current) => ({ ...current, health: event.payload as DashboardSnapshot["health"] }));
      }
    },
    onError: (message) => {
      setLastError(message);
    },
  });

  useEffect(() => {
    if (websocketError) {
      setLastError(websocketError);
    }
  }, [websocketError]);

  const poseAgeMs = snapshot.pose.stamp ? Date.now() - Date.parse(snapshot.pose.stamp) : Number.POSITIVE_INFINITY;
  const canSendGoal =
    snapshot.map.loaded &&
    snapshot.status.localization_ok === true &&
    snapshot.health.action_server_ready &&
    poseAgeMs < 10000;
  const canSetInitialPose = snapshot.map.loaded && snapshot.navigation.state !== "navigating";

  const handleSetInitialPose = async () => {
    if (!selectedGoal) {
      setLastError("请先在地图上点击选点");
      return;
    }
    try {
      const result = await sendInitialPose(selectedGoal);
      setSelectedGoal(result.pose);
      setLastSuccess(result.message);
      setLastError(null);
    } catch (error) {
      setLastSuccess(null);
      setLastError(error instanceof Error ? error.message : "设置初始位姿失败");
    }
  };

  const handleSendGoal = async () => {
    if (!selectedGoal) {
      setLastError("请先在地图上点击目标点");
      return;
    }
    try {
      const navigation = await sendNavigationGoal(selectedGoal);
      setSnapshot((current) => ({ ...current, navigation }));
      setLastSuccess("导航目标已发送");
      setLastError(null);
    } catch (error) {
      setLastSuccess(null);
      setLastError(error instanceof Error ? error.message : "发送导航目标失败");
    }
  };

  const handleCancelGoal = async () => {
    try {
      const navigation = await cancelNavigationGoal();
      setSnapshot((current) => ({ ...current, navigation }));
      setLastSuccess("已发送停止导航请求");
      setLastError(null);
    } catch (error) {
      setLastSuccess(null);
      setLastError(error instanceof Error ? error.message : "停止导航失败");
    }
  };

  return (
    <div className="app-shell">
      <StatusSidebar
        status={snapshot.status}
        pose={snapshot.pose}
        health={snapshot.health}
        backendConnected={backendConnected}
        websocketConnected={websocketConnected}
      />

      <main className="main-panel">
        <header className="topbar">
          <div>
            <h1>A2 Web Console</h1>
            <p>网页监控 + 点选导航 + 停止导航</p>
          </div>
          <div className="topbar-indicators">
            <span className={`indicator ${snapshot.status.system_ready ? "indicator-ok" : "indicator-warn"}`}>
              ready={String(snapshot.status.system_ready)}
            </span>
            <span className={`indicator ${snapshot.status.localization_ok ? "indicator-ok" : "indicator-warn"}`}>
              localization={String(snapshot.status.localization_ok)}
            </span>
          </div>
        </header>

        <MapCanvas
          map={snapshot.map.loaded ? snapshot.map : null}
          pose={snapshot.pose.available ? snapshot.pose : null}
          selectedGoal={selectedGoal}
          activeGoal={snapshot.navigation.goal}
          disabled={!canSendGoal}
          onSelectGoal={setSelectedGoal}
        />
      </main>

      <ControlSidebar
        navigation={snapshot.navigation}
        selectedGoal={selectedGoal}
        canSendGoal={canSendGoal}
        canSetInitialPose={canSetInitialPose}
        onSetInitialPose={handleSetInitialPose}
        onSendGoal={handleSendGoal}
        onCancelGoal={handleCancelGoal}
        lastError={lastError}
        lastSuccess={lastSuccess}
      />
    </div>
  );
}
