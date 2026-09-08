from django import template
from core.pricing_offer_config_v34_1 import public_offer

register = template.Library()


@register.simple_tag
def b1_pricing_offer():
    return public_offer()
