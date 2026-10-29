# -*- coding: utf-8 -*-
"""Localized stool profiles used by the AI analysis result screen.

The profile describes the *typical* features of each model class. It is not a
measurement of the uploaded photo; the frontend displays that caveat.
"""

import json
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROFILE_PATH = os.path.join(_BASE_DIR, 'knowledge', 'stool_profiles.json')
SUPPORTED_LANGUAGES = ('zh-CN', 'zh-TW', 'en', 'pt')

try:
    with open(_PROFILE_PATH, 'r', encoding='utf-8') as _file:
        _DATA = json.load(_file)
except Exception as _error:  # pragma: no cover - only hit if the data file is missing
    print(f"[STOOL] Failed to load {_PROFILE_PATH}: {_error}")
    _DATA = {'profiles': {}, 'shared': {}, 'sources': {}}


def _language(language):
    return language if language in SUPPORTED_LANGUAGES else 'zh-CN'


def _localized(mapping, language):
    if not isinstance(mapping, dict):
        return ''
    lang = _language(language)
    value = mapping.get(lang)
    if value in (None, ''):
        value = mapping.get('zh-CN', '')
    return value


def is_available():
    return bool(_DATA.get('profiles'))


def get_profile(class_id, language='zh-CN'):
    """Return a flat, localized profile for a detector class id, or None."""
    profile = _DATA.get('profiles', {}).get(str(class_id))
    if not profile:
        return None

    shared = _DATA.get('shared', {})
    sources_map = _DATA.get('sources', {})
    sources = []
    for source_id in profile.get('sources', []):
        source = sources_map.get(source_id)
        if source:
            sources.append(source)

    return {
        'key': profile.get('key', ''),
        'name': _localized(profile.get('name'), language),
        'texture': _localized(profile.get('texture'), language),
        'color': _localized(profile.get('color'), language),
        'color_hex': profile.get('color_hex', '#888888'),
        'shape': _localized(profile.get('shape'), language),
        'water': _localized(profile.get('water'), language),
        'risk_label': _localized(profile.get('risk_label'), language),
        'causes': _localized(profile.get('causes'), language) or [],
        'urgency': _localized(profile.get('urgency'), language),
        'vet_advice': _localized(profile.get('vet_advice'), language),
        'care': _localized(profile.get('care'), language),
        'prevention': _localized(profile.get('prevention'), language),
        'red_flags': _localized(shared.get('red_flags'), language) or [],
        'medication_warning': _localized(shared.get('medication_warning'), language),
        'typical_note': _localized(shared.get('typical_note'), language),
        'sources': sources,
    }


def get_profile_for_detection(detection, language='zh-CN'):
    """Map a detector result to a profile, including the no-detection case."""
    if not isinstance(detection, dict):
        return None

    class_id = detection.get('class_id')
    class_name = detection.get('class_name')

    # The detector uses -1 for no detection/error. "未检测到排泄物" should still
    # receive photo guidance; a genuine error should not receive a stool profile.
    if class_id == -1 and class_name == '未检测到排泄物':
        class_id = 3

    return get_profile(class_id, language)
