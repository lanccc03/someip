from enum import StrEnum


class Role(StrEnum):
    CLIENT = "Client"
    SERVER = "Server"


class TransportProtocol(StrEnum):
    TCP = "TCP"
    UDP = "UDP"


class TransmissionType(StrEnum):
    METHOD = "Method"
    EVENT = "Event"
    FIELD = "Field"


class FieldType(StrEnum):
    GETTER = "Getter"
    SETTER = "Setter"
    NOTIFIER = "Notifier"


class SendStrategy(StrEnum):
    TRIGGER = "Trigger"
    CYCLE = "Cycle"


class TraceDirection(StrEnum):
    TX = "TX"
    RX = "RX"
