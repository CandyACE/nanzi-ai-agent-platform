"""实体关系候选表对服务的聚焦测试。"""

from app.services.metadata_relationship_candidate_service import (
    MetadataRelationshipCandidateService,
    RelationshipCandidateGroup,
    RelationshipCandidatePair,
)


def test_parse_schema_filters_examples_and_builds_structural_candidate():
    """精简 Schema 不应携带样例值，结构规则应召回真实外键命名候选。"""
    schema_yaml = """--- [Schema:1] type=table dataset=demo table=orders ---
table_name: orders
table_desc: 订单
columns:
  - name: id
    type: bigint
    pk: true
  - name: user_id
    type: bigint
    term: 用户标识
    examples: [10001, 10002]
    enums:
      - value: 10001
        label: 敏感样例
  - name: order_amount
    type: decimal(12, 2)
    desc: 与关系推导无关的业务字段

--- [Schema:2] type=table dataset=demo table=users ---
table_name: users
table_desc: 用户
columns:
  - name: id
    type: bigint
    pk: true

--- [Schema:3] type=table dataset=demo table=audit_logs ---
table_name: audit_logs
columns:
  - name: event_uuid
    type: varchar
    pk: true
"""

    table_order, table_index = MetadataRelationshipCandidateService.parse_schema(
        schema_yaml
    )
    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )
    groups = MetadataRelationshipCandidateService.group_candidate_pairs(candidates)
    prompt_context = MetadataRelationshipCandidateService.render_group_schema(
        groups[0],
        table_index,
    )

    assert table_order == ["orders", "users", "audit_logs"]
    assert [(pair.left_table, pair.right_table) for pair in candidates] == [
        ("orders", "users")
    ]
    assert "examples" not in prompt_context
    assert "enums" not in prompt_context
    assert "敏感样例" not in prompt_context
    assert "order_amount" not in prompt_context
    assert '"candidate_columns"' in prompt_context
    assert len(prompt_context) < len(schema_yaml)


def test_explicit_foreign_key_builds_high_priority_candidate():
    """显式外键应直接成为高优先级候选，并保留到精简模型上下文。"""
    table_order = ["orders", "users"]
    table_index = {
        "orders": {
            "table_name": "orders",
            "columns": [
                {
                    "name": "owner_ref",
                    "type": "bigint",
                    "foreign_key": "users.id",
                },
                {"name": "amount", "type": "decimal"},
            ],
        },
        "users": {
            "table_name": "users",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
    }

    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )
    groups = MetadataRelationshipCandidateService.group_candidate_pairs(candidates)
    prompt_context = MetadataRelationshipCandidateService.render_group_schema(
        groups[0],
        table_index,
    )

    assert len(candidates) == 1
    assert candidates[0].score == 120
    assert candidates[0].column_pairs == (("owner_ref", "id"),)
    assert "owner_ref" in prompt_context
    assert "amount" not in prompt_context


def test_technical_prefix_does_not_connect_all_tables():
    """共同的 ny 前缀和通用 id 主键不能让无关表成为候选。"""
    table_order = ["ny_member", "ny_member_equity", "ny_package"]
    table_index = {
        "ny_member": {
            "table_name": "ny_member",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
        "ny_member_equity": {
            "table_name": "ny_member_equity",
            "columns": [
                {"name": "id", "type": "bigint", "pk": True},
                {"name": "member_id", "type": "bigint"},
            ],
        },
        "ny_package": {
            "table_name": "ny_package",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
    }

    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )

    assert [(pair.left_table, pair.right_table) for pair in candidates] == [
        ("ny_member", "ny_member_equity")
    ]


def test_compound_table_suffix_alias_recalls_short_foreign_key_name():
    """复合表名应识别省略首段的常见短外键命名。"""
    table_order = ["ny_package_purchase_record", "ny_record_equity"]
    table_index = {
        "ny_package_purchase_record": {
            "table_name": "ny_package_purchase_record",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
        "ny_record_equity": {
            "table_name": "ny_record_equity",
            "columns": [
                {"name": "id", "type": "bigint", "pk": True},
                {"name": "purchase_record_id", "type": "bigint"},
            ],
        },
    }

    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )

    assert len(candidates) == 1
    assert candidates[0].column_pairs == (("id", "purchase_record_id"),)


def test_entity_foreign_key_only_pairs_with_target_primary_key():
    """实体外键不能与目标表其它带 key/code 后缀的普通字段错配。"""
    table_order = ["orders", "members"]
    table_index = {
        "orders": {
            "table_name": "orders",
            "columns": [{"name": "member_id", "type": "bigint"}],
        },
        "members": {
            "table_name": "members",
            "columns": [
                {"name": "id", "type": "bigint", "pk": True},
                {"name": "invitation_code", "type": "bigint"},
                {"name": "parent_member_id", "type": "bigint"},
            ],
        },
    }

    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )

    assert len(candidates) == 1
    assert candidates[0].column_pairs == (("member_id", "id"),)


def test_longer_table_prefix_does_not_steal_shorter_entity_foreign_key():
    """较长复合表名不能把指向较短实体表的外键误判为自身主键关系。"""
    table_order = [
        "ny_member_equity",
        "ny_package_purchase_record",
        "ny_package_purchase_record_equity",
    ]
    table_index = {
        "ny_member_equity": {
            "table_name": "ny_member_equity",
            "columns": [
                {"name": "id", "type": "bigint", "pk": True},
                {"name": "package_purchase_record_id", "type": "bigint"},
            ],
        },
        "ny_package_purchase_record": {
            "table_name": "ny_package_purchase_record",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
        "ny_package_purchase_record_equity": {
            "table_name": "ny_package_purchase_record_equity",
            "columns": [
                {"name": "id", "type": "bigint", "pk": True},
                {"name": "member_equity_id", "type": "bigint"},
            ],
        },
    }

    candidates = MetadataRelationshipCandidateService.build_candidate_pairs(
        table_order,
        table_index,
    )
    candidate_lookup = {
        pair.unordered_key: pair.column_pairs for pair in candidates
    }

    assert candidate_lookup[(
        "ny_member_equity",
        "ny_package_purchase_record",
    )] == (("package_purchase_record_id", "id"),)
    assert candidate_lookup[(
        "ny_member_equity",
        "ny_package_purchase_record_equity",
    )] == (("id", "member_equity_id"),)


def test_candidate_groups_respect_pair_and_table_limits():
    """候选分组必须同时约束表对数和唯一表数量，控制单次模型上下文。"""
    candidates = [
        RelationshipCandidatePair(
            left_table=f"left_{index}",
            right_table=f"right_{index}",
            score=100,
            reasons=("测试键线索",),
        )
        for index in range(10)
    ]

    groups = MetadataRelationshipCandidateService.group_candidate_pairs(
        candidates,
        max_pairs_per_group=8,
        max_tables_per_group=6,
    )

    assert len(groups) == 4
    assert all(len(group.pairs) <= 3 for group in groups)
    assert all(len(group.table_names) <= 6 for group in groups)


def test_validate_relationship_checks_pair_columns_types_and_confidence():
    """AI 输出必须属于候选表对，并引用真实且类型兼容的物理字段。"""
    pair = RelationshipCandidatePair(
        left_table="orders",
        right_table="users",
        score=100,
        reasons=("orders.user_id 指向 users",),
        column_pairs=(("user_id", "id"),),
    )
    group = RelationshipCandidateGroup(
        pairs=(pair,),
        table_names=("orders", "users"),
    )
    table_index = {
        "orders": {
            "table_name": "orders",
            "columns": [{"name": "user_id", "type": "bigint"}],
        },
        "users": {
            "table_name": "users",
            "columns": [{"name": "id", "type": "bigint", "pk": True}],
        },
    }
    valid_relationship = {
        "source_table": "orders",
        "target_table": "users",
        "condition": "orders.user_id = users.id",
        "relation_type": "many_to_one",
        "confidence": 0.96,
    }

    assert MetadataRelationshipCandidateService.validate_relationship(
        valid_relationship,
        group,
        table_index,
    ) == (True, "valid")

    low_confidence = {**valid_relationship, "confidence": 0.5}
    assert MetadataRelationshipCandidateService.validate_relationship(
        low_confidence,
        group,
        table_index,
    ) == (False, "low_confidence")

    missing_column = {
        **valid_relationship,
        "condition": "orders.missing_user_id = users.id",
    }
    assert MetadataRelationshipCandidateService.validate_relationship(
        missing_column,
        group,
        table_index,
    ) == (False, "off_candidate_columns")

    unrelated_column = {
        **valid_relationship,
        "condition": "orders.account_id = users.id",
    }
    table_index["orders"]["columns"].append(
        {"name": "account_id", "type": "bigint"}
    )
    assert MetadataRelationshipCandidateService.validate_relationship(
        unrelated_column,
        group,
        table_index,
    ) == (False, "off_candidate_columns")
