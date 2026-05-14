#ifndef A2_CONTROL_BRIDGE_NODE_HPP
#define A2_CONTROL_BRIDGE_NODE_HPP

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "a2_system/network_utils.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/int32.hpp"
#include "std_msgs/msg/string.hpp"

#if A2_ENABLE_UNITREE_SDK
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/a2/sport/sport_client.hpp>
#endif

class A2ControlBridgeNode : public rclcpp::Node
{
public:
  explicit A2ControlBridgeNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions())
  : Node("a2_control_bridge", options)
  {
    use_mock_ = declare_parameter<bool>("use_mock", true);
    runtime_mode_ = declare_parameter<std::string>("runtime_mode", use_mock_ ? "mock" : "real");
    auto_detect_interface_ = declare_parameter<bool>("auto_detect_interface", true);
    allow_loopback_ = declare_parameter<bool>("allow_loopback", true);
    network_interface_ = declare_parameter<std::string>("network_interface", "");
    interface_candidates_ = declare_parameter<std::vector<std::string>>(
      "interface_candidates", std::vector<std::string>{});
    cmd_topic_ = declare_parameter<std::string>("cmd_topic", "/cmd_vel");
    estop_topic_ = declare_parameter<std::string>("estop_topic", "/a2/estop");
    localization_ok_topic_ = declare_parameter<std::string>("localization_ok_topic", "/a2/localization_ok");
    map_ready_topic_ = declare_parameter<std::string>("map_ready_topic", "/a2/map_ready");
    allow_motion_topic_ = declare_parameter<std::string>("allow_motion_topic", "/a2/allow_motion");
    max_linear_x_ = declare_parameter<double>("max_linear_x", 0.4);
    max_linear_y_ = declare_parameter<double>("max_linear_y", 0.25);
    max_yaw_rate_ = declare_parameter<double>("max_yaw_rate", 0.5);
    cmd_timeout_sec_ = declare_parameter<double>("cmd_timeout_sec", 0.5);
    control_hz_ = declare_parameter<double>("control_hz", 20.0);
    allow_motion_without_map_ = declare_parameter<bool>("allow_motion_without_map", false);
    allow_motion_without_localization_ = declare_parameter<bool>("allow_motion_without_localization", false);
    prepare_balance_stand_ = declare_parameter<bool>("prepare_balance_stand", runtime_mode_ == "real");
    prepare_balance_wait_sec_ = declare_parameter<double>(
      "prepare_balance_wait_sec", runtime_mode_ == "real" ? 2.0 : 0.0);
    sim_cmd_topic_ = declare_parameter<std::string>("sim_cmd_topic", "");
    gait_control_enabled_ = declare_parameter<bool>("gait_control_enabled", false);
    apply_speed_level_ = declare_parameter<bool>("apply_speed_level", true);
    apply_body_height_ = declare_parameter<bool>("apply_body_height", false);
    gait_type_min_ = declare_parameter<int>("gait_type_min", 0);
    gait_type_max_ = declare_parameter<int>("gait_type_max", 7);
    speed_level_min_ = declare_parameter<int>("speed_level_min", 0);
    speed_level_max_ = declare_parameter<int>("speed_level_max", 3);
    body_height_min_ = declare_parameter<double>("body_height_min", -0.10);
    body_height_max_ = declare_parameter<double>("body_height_max", 0.10);
    gait_type_ = clamp_int(declare_parameter<int>("gait_type", 1), gait_type_min_, gait_type_max_);
    speed_level_ = clamp_int(declare_parameter<int>("speed_level", 1), speed_level_min_, speed_level_max_);
    body_height_ = clamp_range(declare_parameter<double>("body_height", 0.0), body_height_min_, body_height_max_);
    gait_type_topic_ = declare_parameter<std::string>("gait_type_topic", "/a2/control/gait_type");
    speed_level_topic_ = declare_parameter<std::string>("speed_level_topic", "/a2/control/speed_level");
    body_height_topic_ = declare_parameter<std::string>("body_height_topic", "/a2/control/body_height");
    gait_state_ = gait_control_enabled_ ? "pending" : "disabled";

    debug_pub_ = create_publisher<geometry_msgs::msg::TwistStamped>("/a2/command_limited", 10);
    control_status_pub_ = create_publisher<std_msgs::msg::String>("/a2/control/status", 10);
    if (!sim_cmd_topic_.empty()) {
      sim_cmd_pub_ = create_publisher<geometry_msgs::msg::Twist>(sim_cmd_topic_, 10);
    }
    cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      cmd_topic_, 10, std::bind(&A2ControlBridgeNode::on_cmd, this, std::placeholders::_1));
    estop_sub_ = create_subscription<std_msgs::msg::Bool>(
      estop_topic_, 10, [this](const std_msgs::msg::Bool::SharedPtr msg) { estop_ = msg->data; });
    localization_sub_ = create_subscription<std_msgs::msg::Bool>(
      localization_ok_topic_, 10, [this](const std_msgs::msg::Bool::SharedPtr msg) { localization_ok_ = msg->data; });
    map_ready_sub_ = create_subscription<std_msgs::msg::Bool>(
      map_ready_topic_, 10, [this](const std_msgs::msg::Bool::SharedPtr msg) { map_ready_ = msg->data; });
    allow_motion_sub_ = create_subscription<std_msgs::msg::Bool>(
      allow_motion_topic_, 10, [this](const std_msgs::msg::Bool::SharedPtr msg) { allow_motion_ = msg->data; });

    // 订阅导航健康监控的速度缩放因子
    auto speed_scale_cb = [this](const std_msgs::msg::Float32::SharedPtr msg) {
      nav_speed_scale_ = std::max(0.0f, std::min(1.0f, msg->data));
    };
    nav_speed_sub_ = this->create_subscription<std_msgs::msg::Float32>(
      "/a2/nav/max_speed_scale", 10, speed_scale_cb);
    gait_type_sub_ = create_subscription<std_msgs::msg::Int32>(
      gait_type_topic_, 10, [this](const std_msgs::msg::Int32::SharedPtr msg) {
        gait_type_ = clamp_int(msg->data, gait_type_min_, gait_type_max_);
        mark_gait_pending();
      });
    speed_level_sub_ = create_subscription<std_msgs::msg::Int32>(
      speed_level_topic_, 10, [this](const std_msgs::msg::Int32::SharedPtr msg) {
        speed_level_ = clamp_int(msg->data, speed_level_min_, speed_level_max_);
        mark_gait_pending();
      });
    body_height_sub_ = create_subscription<std_msgs::msg::Float32>(
      body_height_topic_, 10, [this](const std_msgs::msg::Float32::SharedPtr msg) {
        body_height_ = clamp_range(static_cast<double>(msg->data), body_height_min_, body_height_max_);
        mark_gait_pending();
      });

    resolved_interface_ = resolve_interface();

#if A2_ENABLE_UNITREE_SDK
    if (runtime_mode_ == "real") {
      if (resolved_interface_.empty()) {
        real_interface_ready_ = false;
        RCLCPP_ERROR(get_logger(), "No usable network interface available for real A2 control.");
      } else if (!a2_system::interface_is_ready_for_real(resolved_interface_)) {
        real_interface_ready_ = false;
        RCLCPP_WARN(
          get_logger(),
          "Interface '%s' is not ready for real A2 control. Control bridge will stay in safe no-op mode.",
          resolved_interface_.c_str());
      } else {
        unitree::robot::ChannelFactory::Instance()->Init(0, resolved_interface_);
        sport_client_ = std::make_unique<unitree::robot::a2::SportClient>();
        sport_client_->SetTimeout(25.0F);
        sport_client_->Init();
        RCLCPP_INFO(
          get_logger(), "A2 control bridge initialized with A2 SportClient on interface '%s'.",
          resolved_interface_.c_str());
      }
    }
#endif

    timer_ = create_wall_timer(
      std::chrono::milliseconds(static_cast<int>(1000.0 / std::max(control_hz_, 1.0))),
      std::bind(&A2ControlBridgeNode::control_tick, this));
  }

  // Public for testing
  static double clamp(double value, double limit)
  {
    return std::max(-limit, std::min(value, limit));
  }

  static double clamp_range(double value, double minimum, double maximum)
  {
    if (!std::isfinite(value)) {
      return 0.0;
    }
    if (minimum > maximum) {
      std::swap(minimum, maximum);
    }
    return std::max(minimum, std::min(value, maximum));
  }

  static int clamp_int(int value, int minimum, int maximum)
  {
    if (minimum > maximum) {
      std::swap(minimum, maximum);
    }
    return std::max(minimum, std::min(value, maximum));
  }

  bool motion_gate_open() const
  {
    if (estop_) {
      return false;
    }
    if (!allow_motion_) {
      return false;
    }
    if (!allow_motion_without_localization_ && !localization_ok_) {
      return false;
    }
    if (!allow_motion_without_map_ && !map_ready_) {
      return false;
    }
    return true;
  }

  // Expose member access for testing via topic injection only.
  // All private members remain private; tests interact through ROS topics.

private:
  std::string resolve_interface() const
  {
    if (runtime_mode_ == "gazebo") {
      return "gazebo";
    }
    const bool simulated_mode = runtime_mode_ == "mock" || runtime_mode_ == "gazebo";
    const bool allow_loopback = simulated_mode && allow_loopback_;
    if (!network_interface_.empty() && a2_system::interface_exists(network_interface_)) {
      return network_interface_;
    }
    if (auto_detect_interface_) {
      return a2_system::select_interface(network_interface_, interface_candidates_, allow_loopback);
    }
    return network_interface_;
  }

  void publish_control_status(
    const std::string & state,
    bool ready,
    const std::string & reason)
  {
    std_msgs::msg::String status_msg;
    status_msg.data =
      "mode=" + runtime_mode_ +
      ";state=" + state +
      ";ready=" + std::string(ready ? "true" : "false") +
      ";reason=" + reason +
      ";interface=" + (resolved_interface_.empty() ? "none" : resolved_interface_) +
      ";sport_client=a2" +
      ";gait_backend=unitree_sport" +
      ";gait_control=" + bool_string(gait_control_enabled_) +
      ";gait_type=" + std::to_string(gait_type_) +
      ";speed_level=" + std::to_string(speed_level_) +
      ";body_height=" + format_double(body_height_) +
      ";gait_state=" + status_gait_state() +
      ";last_gait_error=" + last_gait_error_;
    control_status_pub_->publish(status_msg);
    if (status_msg.data != last_control_status_) {
      last_control_status_ = status_msg.data;
      RCLCPP_INFO(get_logger(), "control status: %s", status_msg.data.c_str());
    }
  }

  void on_cmd(const geometry_msgs::msg::Twist::SharedPtr msg)
  {
    latest_cmd_ = *msg;
    last_cmd_time_ = now();
    have_cmd_ = true;
  }

  static std::string bool_string(bool value)
  {
    return value ? "true" : "false";
  }

  static std::string format_double(double value)
  {
    std::ostringstream out;
    out << std::fixed << std::setprecision(3) << value;
    return out.str();
  }

  void mark_gait_pending()
  {
    gait_dirty_ = true;
    gait_applied_ = false;
    last_gait_error_ = "none";
    gait_state_ = gait_control_enabled_ ? "pending" : "disabled";
  }

  std::string status_gait_state() const
  {
    if (!gait_control_enabled_) {
      return "disabled";
    }
    if (runtime_mode_ != "real") {
      return "simulated";
    }
    return gait_state_;
  }

#if A2_ENABLE_UNITREE_SDK
  bool apply_real_gait_controls()
  {
    if (!gait_control_enabled_) {
      gait_state_ = "disabled";
      return true;
    }
    if (!gait_dirty_ && gait_applied_) {
      gait_state_ = "applied";
      return true;
    }

    if (apply_speed_level_) {
      const auto speed_code = sport_client_->SpeedLevel(speed_level_);
      if (speed_code != 0) {
        gait_state_ = "error";
        last_gait_error_ = "speed_level_failed:" + std::to_string(speed_code);
        publish_control_status("error", false, last_gait_error_);
        RCLCPP_ERROR(
          get_logger(), "SpeedLevel(%d) failed with code %d on interface '%s'.",
          speed_level_, speed_code, resolved_interface_.c_str());
        return false;
      }
    }

    if (apply_body_height_) {
      const auto height_code = sport_client_->BodyHeight(static_cast<float>(body_height_));
      if (height_code != 0) {
        gait_state_ = "error";
        last_gait_error_ = "body_height_failed:" + std::to_string(height_code);
        publish_control_status("error", false, last_gait_error_);
        RCLCPP_ERROR(
          get_logger(), "BodyHeight(%.3f) failed with code %d on interface '%s'.",
          body_height_, height_code, resolved_interface_.c_str());
        return false;
      }
    }

    const auto gait_code = sport_client_->SwitchGait(gait_type_);
    if (gait_code != 0) {
      gait_state_ = "error";
      last_gait_error_ = "switch_gait_failed:" + std::to_string(gait_code);
      publish_control_status("error", false, last_gait_error_);
      RCLCPP_ERROR(
        get_logger(), "SwitchGait(%d) failed with code %d on interface '%s'.",
        gait_type_, gait_code, resolved_interface_.c_str());
      return false;
    }

    gait_dirty_ = false;
    gait_applied_ = true;
    gait_state_ = "applied";
    last_gait_error_ = "none";
    RCLCPP_INFO(
      get_logger(),
      "A2 gait controls applied: gait_type=%d speed_level=%d apply_body_height=%s body_height=%.3f.",
      gait_type_, speed_level_, apply_body_height_ ? "true" : "false", body_height_);
    return true;
  }
#endif

  void control_tick()
  {
    geometry_msgs::msg::Twist limited;
    const bool timed_out = !have_cmd_ || (now() - last_cmd_time_).seconds() > cmd_timeout_sec_;
    const bool gate_open = motion_gate_open();

    if (!timed_out && gate_open) {
      limited.linear.x = clamp(latest_cmd_.linear.x, max_linear_x_);
      limited.linear.y = clamp(latest_cmd_.linear.y, max_linear_y_);
      limited.angular.z = clamp(latest_cmd_.angular.z, max_yaw_rate_);
      // 应用导航健康监控的速度缩放
      limited.linear.x *= nav_speed_scale_;
      limited.linear.y *= nav_speed_scale_;
      limited.angular.z *= nav_speed_scale_;
    }

    geometry_msgs::msg::TwistStamped debug;
    debug.header.stamp = now();
    debug.header.frame_id = "base_link";
    debug.twist = limited;
    debug_pub_->publish(debug);
    if (sim_cmd_pub_) {
      sim_cmd_pub_->publish(limited);
    }

    std::string status_state = "idle";
    std::string status_reason = "cmd_timeout";
    bool status_ready = true;
    if (!gate_open) {
      status_state = "blocked";
      status_reason = estop_ ? "estop" :
        (!allow_motion_ ? "allow_motion_false" :
        (!localization_ok_ ? "localization_not_ready" : "map_not_ready"));
      status_ready = false;
    } else if (!timed_out) {
      const bool active = std::fabs(limited.linear.x) > 1e-3 || std::fabs(limited.linear.y) > 1e-3 ||
        std::fabs(limited.angular.z) > 1e-3;
      status_state = active ? "ready" : "idle";
      status_reason = active ? "command_active" : "command_zero";
    }

    if (!gate_open) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 3000,
        "Motion rejected. estop=%s allow_motion=%s localization_ok=%s map_ready=%s",
        estop_ ? "true" : "false",
        allow_motion_ ? "true" : "false",
        localization_ok_ ? "true" : "false",
        map_ready_ ? "true" : "false");
    }

    if (runtime_mode_ != "real") {
      const bool active = std::fabs(limited.linear.x) > 1e-3 || std::fabs(limited.linear.y) > 1e-3 ||
        std::fabs(limited.angular.z) > 1e-3;
      if (gait_control_enabled_) {
        gait_state_ = "simulated";
      }
      publish_control_status(status_state, status_ready, status_reason);
      RCLCPP_INFO_THROTTLE(
        get_logger(), *get_clock(), 2000,
        "Simulated control tick: mode=%s active=%s vx=%.3f vy=%.3f wz=%.3f interface='%s'",
        runtime_mode_.c_str(),
        active ? "true" : "false", limited.linear.x, limited.linear.y, limited.angular.z,
        resolved_interface_.c_str());
      return;
    }

#if A2_ENABLE_UNITREE_SDK
    if (!real_interface_ready_) {
      publish_control_status("waiting_interface", false, resolved_interface_.empty() ? "no_interface" : "interface_not_ready");
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 5000,
        "Real interface '%s' is not ready. Control bridge remains in diagnostic idle mode.",
        resolved_interface_.c_str());
      return;
    }

    if (!sport_client_) {
      publish_control_status("error", false, "sport_client_unavailable");
      RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 3000, "Sport client unavailable in real mode.");
      return;
    }

    const bool active = std::fabs(limited.linear.x) > 1e-3 || std::fabs(limited.linear.y) > 1e-3 ||
      std::fabs(limited.angular.z) > 1e-3;

    const auto current_time = now();

    if (prepare_balance_stand_ && !prepared_) {
      if (preparing_) {
        const double elapsed = (current_time - prepare_started_at_).seconds();
        if (elapsed >= prepare_balance_wait_sec_) {
          prepared_ = true;
          preparing_ = false;
          RCLCPP_INFO(
            get_logger(),
            "Balance stand preparation completed after %.2fs on interface '%s'.",
            elapsed, resolved_interface_.c_str());
        } else {
          publish_control_status("preparing", false, "balance_stand_wait");
          return;
        }
      } else if (active) {
        const auto balance_code = sport_client_->BalanceStand();
        if (balance_code != 0) {
          publish_control_status("error", false, "balance_stand_failed");
          RCLCPP_ERROR(
            get_logger(),
            "BalanceStand failed with code %d on interface '%s'.",
            balance_code, resolved_interface_.c_str());
          return;
        }
        preparing_ = true;
        prepare_started_at_ = current_time;
        publish_control_status("preparing", false, "balance_stand");
        RCLCPP_INFO(
          get_logger(),
          "BalanceStand triggered on interface '%s'; waiting %.2fs before Move().",
          resolved_interface_.c_str(), prepare_balance_wait_sec_);
        return;
      }
    }

    if (!active) {
      publish_control_status(status_state, status_ready, status_reason);
      if (was_active_) {
        const auto stop_code = sport_client_->StopMove();
        if (stop_code != 0) {
          RCLCPP_WARN(
            get_logger(),
            "StopMove returned code %d on interface '%s'.",
            stop_code, resolved_interface_.c_str());
        }
        was_active_ = false;
      }
      return;
    }

    if (!apply_real_gait_controls()) {
      return;
    }

    const auto move_code = sport_client_->Move(
      static_cast<float>(limited.linear.x),
      static_cast<float>(limited.linear.y),
      static_cast<float>(limited.angular.z));
    if (move_code != 0) {
      publish_control_status("error", false, "move_failed");
      RCLCPP_ERROR(
        get_logger(),
        "Move(vx=%.3f, vy=%.3f, wz=%.3f) failed with code %d on interface '%s'.",
        limited.linear.x, limited.linear.y, limited.angular.z, move_code,
        resolved_interface_.c_str());
      return;
    }
    was_active_ = true;
    publish_control_status("ready", true, "command_sent");
#else
    publish_control_status("error", false, "sdk_library_missing");
    RCLCPP_ERROR_THROTTLE(
      get_logger(), *get_clock(), 3000,
      "Real control requested but this binary was built without unitree_sdk2.");
#endif
  }

  bool use_mock_{true};
  std::string runtime_mode_{"mock"};
  bool auto_detect_interface_{true};
  bool allow_loopback_{true};
  bool allow_motion_without_map_{false};
  bool allow_motion_without_localization_{false};
  bool prepare_balance_stand_{false};
  bool preparing_{false};
  bool real_interface_ready_{true};
  bool gait_control_enabled_{false};
  bool apply_speed_level_{true};
  bool apply_body_height_{false};
  bool gait_dirty_{true};
  bool gait_applied_{false};
  bool have_cmd_{false};
  bool allow_motion_{true};
  bool map_ready_{false};
  bool localization_ok_{false};
  bool estop_{false};
  bool prepared_{false};
  bool was_active_{false};

  std::string network_interface_;
  std::vector<std::string> interface_candidates_;
  std::string resolved_interface_;
  std::string cmd_topic_;
  std::string estop_topic_;
  std::string localization_ok_topic_;
  std::string map_ready_topic_;
  std::string allow_motion_topic_;
  std::string sim_cmd_topic_;
  std::string gait_type_topic_;
  std::string speed_level_topic_;
  std::string body_height_topic_;
  std::string gait_state_{"disabled"};
  std::string last_gait_error_{"none"};

  double max_linear_x_{0.4};
  double max_linear_y_{0.25};
  double max_yaw_rate_{0.5};
  double cmd_timeout_sec_{0.5};
  double control_hz_{20.0};
  double prepare_balance_wait_sec_{0.0};
  double body_height_{0.0};
  double body_height_min_{-0.10};
  double body_height_max_{0.10};
  int gait_type_{1};
  int gait_type_min_{0};
  int gait_type_max_{7};
  int speed_level_{1};
  int speed_level_min_{0};
  int speed_level_max_{3};
  float nav_speed_scale_{1.0f};

  geometry_msgs::msg::Twist latest_cmd_;
  rclcpp::Time last_cmd_time_{0, 0, RCL_ROS_TIME};
  rclcpp::Time prepare_started_at_{0, 0, RCL_ROS_TIME};

  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr estop_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr localization_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr map_ready_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr allow_motion_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr nav_speed_sub_;
  rclcpp::Subscription<std_msgs::msg::Int32>::SharedPtr gait_type_sub_;
  rclcpp::Subscription<std_msgs::msg::Int32>::SharedPtr speed_level_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr body_height_sub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr debug_pub_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr sim_cmd_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr control_status_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::string last_control_status_;

#if A2_ENABLE_UNITREE_SDK
  std::unique_ptr<unitree::robot::a2::SportClient> sport_client_;
#endif
};

#endif  // A2_CONTROL_BRIDGE_NODE_HPP
