from enum import Enum
import strawberry
from novu.enums import PushProviderIdEnum, EmailProviderIdEnum, Channel


@strawberry.enum
class NotificationType(Enum):
    PR = strawberry.enum_value("PR", description="POST_REACTION")
    PC = strawberry.enum_value("PC", description="POST_COMMENT")
    PCR = strawberry.enum_value("PCR", description="POST_COMMENT_REPLY")
    PCRA = strawberry.enum_value("PCRA", description="POST_COMMENT_REACTION")
    CR = strawberry.enum_value("CR", description="CONNECTION_REQUEST")
    CA = strawberry.enum_value("CA", description="CONNECTION_ACCEPTED")
    CC = strawberry.enum_value("CC", description="CONNECTION_CONFIRMED")
    F = strawberry.enum_value("F", description="FOLLOW")
    FR = strawberry.enum_value("FR", description="FOLLOW_REQUEST")
    FRA = strawberry.enum_value("FRA", description="FOLLOW_REQUEST_APPROVED")
    CMR = strawberry.enum_value("CMR", description="COMMUNITY_MEMBERSHIP_REQUEST")
    CMRA = strawberry.enum_value("CMRA", description="COMMUNITY_MEMBERSHIP_APPROVED")
    CMRE = strawberry.enum_value("CMRE", description="COMMUNITY_MEMBERSHIP_REVOKED")
    CAPG = strawberry.enum_value("CAPG", description="COMMUNITY_ADMIN_PRIVILEGES_GRANTED")
    CAPR = strawberry.enum_value("CAPR", description="COMMUNITY_ADMIN_PRIVILEGES_REVOKED")
    CI = strawberry.enum_value("CI", description="COMMUNITY_INVITE")
    CID = strawberry.enum_value("CID", description="COMMUNITY_INVITE_DECLINED")
    PUM = strawberry.enum_value("PUM", description="POST_USER_MENTION")
    PCUM = strawberry.enum_value("PCUM", description="POST_COMMENT_USER_MENTION")
    CNP = strawberry.enum_value("CNP", description="COMMUNITY_NEW_POST")
    UNP = strawberry.enum_value("UNP", description="USER_NEW_POST")
    REL = strawberry.enum_value("REL", description="RELEASE_INFO")


class NotificationProvider(Enum):
    APNS = PushProviderIdEnum.APNS
    FCM = PushProviderIdEnum.FCM
    EMAIL = EmailProviderIdEnum.CUSTOM_SMTP


class NotificationChannel(Enum):
    IN_APP = Channel.IN_APP
