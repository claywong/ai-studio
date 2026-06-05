#!/usr/bin/env zsh
# 生成用户使用情况报告（4-17 到 4-27）
# cost 字段使用 account_cost（来自 user-breakdown，最近7天）

set -euo pipefail

source /Users/wangzhong/workspace/tool/ai-studio/.env
BASE_URL=$(echo "$SUB2API_BASE_URL" | sed 's|/api/v1||')
KEY="$SUB2API_ADMIN_API_KEY"

START="2026-04-17"
END="2026-04-27"

# 目标用户 ID 列表（不含甘崇志）
TARGET_IDS='[57,74,62,63,58,70,65,66,61,82,59,56,12,179,60,49,81,84]'

# 用户名映射（id -> 姓名）
declare -A NAMES=(
  [57]="徐典阳" [74]="何丽"   [62]="罗宇"   [63]="刘超"
  [58]="唐嗣元" [70]="唐禄棕" [65]="王高利" [66]="袁鑫"
  [61]="邓夫伟" [82]="罗永康" [59]="王凯"   [56]="陈伟"
  [12]="何佳诚" [179]="宋永进" [60]="曾洋"  [49]="李贝贝"
  [81]="熊锐莉" [84]="张艳蓉"
)

echo "正在获取数据..."

# 1. user-breakdown：获取 account_cost / actual_cost / tokens / requests（最近7天）
BREAKDOWN=$(curl -s -H "x-api-key: ${KEY}" "${BASE_URL}/api/v1/admin/dashboard/user-breakdown")
BREAKDOWN_START=$(echo "$BREAKDOWN" | jq -r '.data.start_date')
BREAKDOWN_END=$(echo "$BREAKDOWN" | jq -r '.data.end_date')

# 2. users-usage：获取指定时间段的 actual_cost（4-17 到 4-27）
USAGE=$(curl -s -X POST \
  -H "x-api-key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"start\":\"${START}\",\"end\":\"${END}\",\"user_ids\":${TARGET_IDS}}" \
  "${BASE_URL}/api/v1/admin/dashboard/users-usage")

echo ""
echo "============================================================"
echo "  用户使用情况报告"
echo "  users-usage 时间段：${START} 至 ${END}"
echo "  user-breakdown 时间段：${BREAKDOWN_START} 至 ${BREAKDOWN_END}（最近7天）"
echo "============================================================"
printf "\n%-4s %-10s %14s %14s %14s %10s\n" \
  "排名" "用户名" "actual_cost(元)" "account_cost(元)" "Token总量" "请求数"
echo "------------------------------------------------------------"

# 用 jq 合并两份数据，按 actual_cost(4-17~4-27) 排序输出
jq -n \
  --argjson ids "$TARGET_IDS" \
  --argjson breakdown "$BREAKDOWN" \
  --argjson usage "$USAGE" \
  '
  # 构建 breakdown 索引 {user_id: {account_cost, actual_cost, tokens, requests}}
  ($breakdown.data.users | map({key: (.user_id|tostring), value: .}) | from_entries) as $bd |

  # 构建 usage 索引 {user_id: {total_actual_cost}}
  ($usage.data.stats) as $us |

  # 合并，按 actual_cost(usage) 排序
  [ $ids[] |
    . as $id |
    {
      id: $id,
      actual_cost_range: ($us[($id|tostring)].total_actual_cost // 0),
      account_cost_7d:   ($bd[($id|tostring)].account_cost // null),
      actual_cost_7d:    ($bd[($id|tostring)].actual_cost  // null),
      tokens:            ($bd[($id|tostring)].total_tokens  // null),
      requests:          ($bd[($id|tostring)].requests      // null)
    }
  ] | sort_by(-.actual_cost_range)
  ' | \
jq -r 'to_entries[] | "\(.key+1)\t\(.value.id)\t\(.value.actual_cost_range)\t\(.value.account_cost_7d)\t\(.value.actual_cost_7d)\t\(.value.tokens)\t\(.value.requests)"' | \
while IFS=$'\t' read -r rank id actual_range account_7d actual_7d tokens requests; do
  name="${NAMES[$id]:-ID:$id}"
  # 格式化数字
  fmt_actual=$(printf "%.2f" "$actual_range" 2>/dev/null || echo "$actual_range")
  fmt_account=$([ "$account_7d" = "null" ] && echo "  -" || printf "%.2f" "$account_7d")
  fmt_tokens=$([ "$tokens" = "null" ] && echo "  -" || printf "%'.0f" "$tokens" 2>/dev/null || echo "$tokens")
  fmt_req=$([ "$requests" = "null" ] && echo "  -" || echo "$requests")
  printf "%-4s %-10s %14s %14s %14s %10s\n" \
    "$rank" "$name" "$fmt_actual" "$fmt_account" "$fmt_tokens" "$fmt_req"
done

echo "------------------------------------------------------------"

# 汇总
TOTAL_ACTUAL=$(jq -r '[.data.stats | to_entries[] | select(.key | IN("57","74","62","63","58","70","65","66","61","82","59","56","12","179","60","49","81","84")) | .value.total_actual_cost] | add' <<< "$USAGE")
TOTAL_ACCOUNT=$(echo "$BREAKDOWN" | jq --argjson ids "$TARGET_IDS" '[.data.users[] | select(.user_id as $id | $ids | index($id) != null) | .account_cost] | add')
TOTAL_TOKENS=$(echo "$BREAKDOWN" | jq --argjson ids "$TARGET_IDS" '[.data.users[] | select(.user_id as $id | $ids | index($id) != null) | .total_tokens] | add')
TOTAL_REQ=$(echo "$BREAKDOWN" | jq --argjson ids "$TARGET_IDS" '[.data.users[] | select(.user_id as $id | $ids | index($id) != null) | .requests] | add')

printf "%-4s %-10s %14s %14s %14s %10s\n" \
  "合计" "18人" \
  "$(printf '%.2f' "$TOTAL_ACTUAL")" \
  "$(printf '%.2f' "$TOTAL_ACCOUNT")" \
  "$(printf '%d' "$TOTAL_TOKENS")" \
  "$TOTAL_REQ"

echo ""
echo "说明："
echo "  actual_cost(元)  = users-usage API，时间段 ${START}~${END}"
echo "  account_cost(元) = user-breakdown API，时间段 ${BREAKDOWN_START}~${BREAKDOWN_END}（固定最近7天）"
echo "  Token / 请求数   = user-breakdown API，同上（未进入 Top50 活跃用户显示 -）"
echo "============================================================"
