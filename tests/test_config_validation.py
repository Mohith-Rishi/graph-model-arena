"""Tests for GraphConfig and GameConfig validation."""

import pytest

from graph_model_arena.models import GameConfig, GraphConfig


class TestGraphConfigValidation:
    def test_valid_defaults(self):
        GraphConfig().validate()

    def test_num_nodes_too_low(self):
        with pytest.raises(ValueError, match="num_nodes"):
            GraphConfig(num_nodes=19).validate()

    def test_num_nodes_too_high(self):
        with pytest.raises(ValueError, match="num_nodes"):
            GraphConfig(num_nodes=201).validate()

    def test_num_nodes_boundaries(self):
        GraphConfig(num_nodes=20).validate()
        GraphConfig(num_nodes=200).validate()

    def test_probability_out_of_range(self):
        with pytest.raises(ValueError, match="trap_probability"):
            GraphConfig(trap_probability=-0.1).validate()
        with pytest.raises(ValueError, match="clue_probability"):
            GraphConfig(clue_probability=1.1).validate()

    def test_edge_density_out_of_range(self):
        with pytest.raises(ValueError, match="edge_density"):
            GraphConfig(edge_density=-0.1).validate()
        with pytest.raises(ValueError, match="edge_density"):
            GraphConfig(edge_density=1.1).validate()

    def test_obstacle_density_out_of_range(self):
        with pytest.raises(ValueError, match="obstacle_density"):
            GraphConfig(obstacle_density=-0.1).validate()

    def test_map_reveal_depth_out_of_range(self):
        with pytest.raises(ValueError, match="map_reveal_depth"):
            GraphConfig(map_reveal_depth=0).validate()
        with pytest.raises(ValueError, match="map_reveal_depth"):
            GraphConfig(map_reveal_depth=4).validate()

    def test_map_reveal_depth_boundaries(self):
        GraphConfig(map_reveal_depth=1).validate()
        GraphConfig(map_reveal_depth=3).validate()


class TestGameConfigValidation:
    def test_valid_defaults(self):
        GameConfig().validate()

    def test_num_models_too_low(self):
        with pytest.raises(ValueError, match="num_models"):
            GameConfig(num_models=1).validate()

    def test_num_models_too_high(self):
        with pytest.raises(ValueError, match="num_models"):
            GameConfig(num_models=9).validate()

    def test_num_models_boundaries(self):
        GameConfig(num_models=2).validate()
        GameConfig(num_models=8).validate()

    def test_max_turns_zero(self):
        with pytest.raises(ValueError, match="max_turns"):
            GameConfig(max_turns=0).validate()

    def test_timeout_zero(self):
        with pytest.raises(ValueError, match="move_timeout_seconds"):
            GameConfig(move_timeout_seconds=0).validate()

    def test_invalid_graph_config_propagates(self):
        with pytest.raises(ValueError, match="num_nodes"):
            GameConfig(graph_config=GraphConfig(num_nodes=5)).validate()
