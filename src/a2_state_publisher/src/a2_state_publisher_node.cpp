#include <memory>
#include <string>
#include <vector>

#include "a2_interfaces/msg/robot_state.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "tf2_ros/transform_broadcaster.h"

class A2StatePublisherNode : public rclcpp::Node
{
public:
  A2StatePublisherNode()
  : Node("a2_state_publisher")
  {
    input_topic_ = declare_parameter<std::string>("input_topic", "/a2/raw_state");
    state_topic_ = declare_parameter<std::string>("state_topic", "/robot_state");
    imu_topic_ = declare_parameter<std::string>("imu_topic", "/imu/data");
    odom_topic_ = declare_parameter<std::string>("odom_topic", "/odom");
    joint_state_topic_ = declare_parameter<std::string>("joint_state_topic", "/joint_states");
    odom_frame_ = declare_parameter<std::string>("odom_frame", "odom");
    base_frame_ = declare_parameter<std::string>("base_frame", "base_link");
    imu_frame_ = declare_parameter<std::string>("imu_frame", "imu_link");
    publish_tf_ = declare_parameter<bool>("publish_tf", true);
    publish_joint_states_ = declare_parameter<bool>("publish_joint_states", false);
    flatten_z_in_odom_ = declare_parameter<bool>("flatten_z_in_odom", true);
    joint_names_ = declare_parameter<std::vector<std::string>>(
      "joint_names",
      {"FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
       "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
       "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
       "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint"});

    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>(imu_topic_, 20);
    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>(odom_topic_, 20);
    state_pub_ = create_publisher<a2_interfaces::msg::RobotState>(state_topic_, 20);
    if (publish_joint_states_) {
      joint_pub_ = create_publisher<sensor_msgs::msg::JointState>(joint_state_topic_, 10);
    }
    if (publish_tf_) {
      tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    }

    state_sub_ = create_subscription<a2_interfaces::msg::RobotState>(
      input_topic_, 20,
      std::bind(&A2StatePublisherNode::on_state, this, std::placeholders::_1));
  }

private:
  void on_state(const a2_interfaces::msg::RobotState::SharedPtr msg)
  {
    state_pub_->publish(*msg);

    sensor_msgs::msg::Imu imu;
    imu.header.stamp = msg->stamp;
    imu.header.frame_id = imu_frame_;
    imu.orientation.x = msg->orientation_xyzw[0];
    imu.orientation.y = msg->orientation_xyzw[1];
    imu.orientation.z = msg->orientation_xyzw[2];
    imu.orientation.w = msg->orientation_xyzw[3];
    imu.angular_velocity.x = msg->angular_velocity[0];
    imu.angular_velocity.y = msg->angular_velocity[1];
    imu.angular_velocity.z = msg->angular_velocity[2];
    imu.linear_acceleration.x = msg->linear_acceleration[0];
    imu.linear_acceleration.y = msg->linear_acceleration[1];
    imu.linear_acceleration.z = msg->linear_acceleration[2];
    imu_pub_->publish(imu);

    nav_msgs::msg::Odometry odom;
    odom.header.stamp = msg->stamp;
    odom.header.frame_id = odom_frame_;
    odom.child_frame_id = base_frame_;
    odom.pose.pose.position.x = msg->position[0];
    odom.pose.pose.position.y = msg->position[1];
    odom.pose.pose.position.z = flatten_z_in_odom_ ? 0.0 : msg->position[2];
    odom.pose.pose.orientation.x = msg->orientation_xyzw[0];
    odom.pose.pose.orientation.y = msg->orientation_xyzw[1];
    odom.pose.pose.orientation.z = msg->orientation_xyzw[2];
    odom.pose.pose.orientation.w = msg->orientation_xyzw[3];
    odom.twist.twist.linear.x = msg->velocity[0];
    odom.twist.twist.linear.y = msg->velocity[1];
    odom.twist.twist.linear.z = msg->velocity[2];
    odom.twist.twist.angular.z = msg->yaw_speed;
    odom_pub_->publish(odom);

    if (publish_joint_states_) {
      sensor_msgs::msg::JointState joints;
      joints.header.stamp = msg->stamp;
      joints.name = joint_names_;
      joints.position.assign(joint_names_.size(), 0.0);
      joints.velocity.assign(joint_names_.size(), 0.0);
      joints.effort.assign(joint_names_.size(), 0.0);
      joint_pub_->publish(joints);
    }

    if (publish_tf_ && tf_broadcaster_ != nullptr) {
      geometry_msgs::msg::TransformStamped transform;
      transform.header.stamp = msg->stamp;
      transform.header.frame_id = odom_frame_;
      transform.child_frame_id = base_frame_;
      transform.transform.translation.x = msg->position[0];
      transform.transform.translation.y = msg->position[1];
      transform.transform.translation.z = flatten_z_in_odom_ ? 0.0 : msg->position[2];
      transform.transform.rotation.x = msg->orientation_xyzw[0];
      transform.transform.rotation.y = msg->orientation_xyzw[1];
      transform.transform.rotation.z = msg->orientation_xyzw[2];
      transform.transform.rotation.w = msg->orientation_xyzw[3];
      tf_broadcaster_->sendTransform(transform);
    }
  }

  std::string input_topic_;
  std::string state_topic_;
  std::string imu_topic_;
  std::string odom_topic_;
  std::string joint_state_topic_;
  std::string odom_frame_;
  std::string base_frame_;
  std::string imu_frame_;
  bool publish_tf_{true};
  bool publish_joint_states_{false};
  bool flatten_z_in_odom_{true};
  std::vector<std::string> joint_names_;

  rclcpp::Subscription<a2_interfaces::msg::RobotState>::SharedPtr state_sub_;
  rclcpp::Publisher<a2_interfaces::msg::RobotState>::SharedPtr state_pub_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr joint_pub_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<A2StatePublisherNode>());
  rclcpp::shutdown();
  return 0;
}
