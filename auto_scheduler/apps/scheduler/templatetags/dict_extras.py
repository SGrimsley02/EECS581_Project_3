'''
Name: apps/scheduler/templatetags/dict_extras.py
Description: Let template access dictionary items by key.
Authors: Kiara Grimsley
Created: November 16, 2025
Last Modified: November 16, 2025
'''

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)