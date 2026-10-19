"""OFX serializers for BTG statement data.

Available engines that can be selected with --backend:

- plain: hand-rolled OFX v1 (SGML) builder, no extra dependencies.
- ofxtools: serializer backed by the ofxtools library; supports both
  OFX v1 and v2. Requires the [ofxtools] optional dependency.
"""
