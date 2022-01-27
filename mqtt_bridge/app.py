import inject
import paho.mqtt.client as mqtt
#import rospy
import rclpy
from rclpy.node import Node

from .bridge import create_bridge
from .mqtt_client import create_private_path_extractor
from .util import lookup_object


def create_config(mqtt_client, serializer, deserializer, mqtt_private_path):
    if isinstance(serializer, str):
        serializer = lookup_object(serializer)
    if isinstance(deserializer, str):
        deserializer = lookup_object(deserializer)
    private_path_extractor = create_private_path_extractor(mqtt_private_path)
    def config(binder):
        binder.bind('serializer', serializer)
        binder.bind('deserializer', deserializer)
        binder.bind(mqtt.Client, mqtt_client)
        binder.bind('mqtt_private_path_extractor', private_path_extractor)
    return config


def mqtt_bridge_node():
    # init node
    #rospy.init_node('mqtt_bridge_node')
    global mqtt_node 
    mqtt_node = Node('mqtt_bridge_node',
                allow_undeclared_parameters=True,
                automatically_declare_parameters_from_overrides=True)

    # load bridge parameters
    bridge_dict_keys = ["factory","msg_type","topic_from","topic_to"]
    bridge_params = []
    bridges_list = filter(lambda key: key[:7] == "bridge.", mqtt_node._parameters.keys())
    for bridge_name in bridges_list:
        bridge_param = mqtt_node.get_parameter(bridge_name).value
        bridge_params.append(dict(zip(bridge_dict_keys,bridge_param)))

    #params = rospy.get_param("~", {})
    #mqtt_params = params.pop("mqtt", {})
    mqtt_params ={
                    "client" :  mqtt_node.get_parameters_by_prefix("mqtt.client"),
                    "tls" : mqtt_node.get_parameters_by_prefix("mqtt.tls"),
                    "account" : mqtt_node.get_parameters_by_prefix("mqtt.account"),
                    "userdata" : mqtt_node.get_parameters_by_prefix("mqtt.userdata"),
                    "message" : mqtt_node.get_parameters_by_prefix("mqtt.message"),
                    "will"  : mqtt_node.get_parameters_by_prefix("mqtt.will")
                }
    #conn_params = mqtt_params.pop("connection")
    conn_params = mqtt_node.get_parameters_by_prefix("mqtt.connection")
    for key in conn_params.keys():
        conn_params.update({key : conn_params[key].value})

    #mqtt_private_path = mqtt_params.pop("private_path", "")
    mqtt_private_path = mqtt_node.get_parameter("mqtt.private_path").value
    #bridge_params = params.get("bridge", [])

    # create mqtt client
    #mqtt_client_factory_name = rospy.get_param(
    #    "~mqtt_client_factory", ".mqtt_client:default_mqtt_client_factory")
    mqtt_client_factory_name = mqtt_node.get_parameter_or(
        "~mqtt_client_factory", ".mqtt_client:default_mqtt_client_factory")
    mqtt_client_factory = lookup_object(mqtt_client_factory_name)
    mqtt_client = mqtt_client_factory(mqtt_params)

    # load serializer and deserializer
    serializer = mqtt_node.get_parameter_or('serializer', 'msgpack:dumps')
    #serializer = params.get('serializer', 'msgpack:dumps')
    deserializer = mqtt_node.get_parameter_or('deserializer', 'msgpack:loads')
    #deserializer = params.get('deserializer', 'msgpack:loads')

    # dependency injection
    config = create_config(
        mqtt_client, serializer, deserializer, mqtt_private_path)
    inject.configure(config)

    # configure and connect to MQTT broker
    mqtt_client.on_connect = _on_connect
    mqtt_client.on_disconnect = _on_disconnect
    mqtt_client.connect(**conn_params)

    # configure bridges
    bridges = []
    for bridge_args in bridge_params:
        bridges.append(create_bridge(**bridge_args,ros_node=mqtt_node))

    # start MQTT loop
    mqtt_client.loop_start()

    # register shutdown callback and spin
    """rospy.on_shutdown(mqtt_client.disconnect)
    rospy.on_shutdown(mqtt_client.loop_stop)
    rospy.spin()"""

    try:
        rclpy.spin(mqtt_node)
    except KeyboardInterrupt:
        mqtt_node.get_logger().info('Ctrl-C detected')
        mqtt_client.disconnect
        mqtt_client.loop_stop

    mqtt_node.destroy_node()


def _on_connect(client, userdata, flags, response_code):
    mqtt_node.get_logger().info('MQTT connected')


def _on_disconnect(client, userdata, response_code):
    mqtt_node.get_logger().info('MQTT disconnected')


__all__ = ['mqtt_bridge_node']