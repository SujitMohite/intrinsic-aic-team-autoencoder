"""data_collection_v2 — keystone scripted-CheatCode data pipeline (v2).

Architecture: see plan at /home/smohite/.claude/plans/i-have-done-previously-cheeky-bubble.md
Strategy: context/10_data/02_offline_scripted_groundtruth.md
24h plan:  context/11_24h_strategy/01_data_24h.md

v2 key difference vs v1: ONE container, ONE engine process, ONE aic_model, ONE recorder
for an entire session of N trials. The engine's native trial loop (aic_engine.cpp:583-615)
handles per-trial reset (delete entities, home robot, respawn scene) without restarting
Gazebo or any subprocess.
"""
