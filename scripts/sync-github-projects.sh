#!/bin/bash
# 同步 PyUploadX 任务到 GitHub Projects #4（用户级 Projects v2，PROJ-PYUPX-0001）。
# 用法: scripts/sync-github-projects.sh [items.tsv]
#   items.tsv 每行: 标题<TAB>状态<TAB>[优先级]；状态 ∈ 未开始|进行中|已完成，优先级 ∈ P0|P1|P2（可空）。
# 前置: Classic PAT（project scope）写入 /tmp/gh_token（chmod 600）。
# 幂等：按标题匹配，缺失创建，存在只更新字段。字段/选项 ID 每次自动发现。
set -uo pipefail
TSV="${1:-/tmp/sync-items.tsv}"
TOKEN=$(cat /tmp/gh_token)
API=https://api.github.com/graphql
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
OWNER=shark8848
PROJ_NUMBER=4

gql() { curl -sS --max-time 30 "${AUTH[@]}" "$API" -d "$1"; }

# 项目 node ID
PROJ=$(gql '{"query":"query{user(login:\"'"$OWNER"'\"){projectV2(number:'"$PROJ_NUMBER"'){id title}}}"}' \
  | jq -r '.data.user.projectV2.id')
[ -n "$PROJ" ] && [ "$PROJ" != "null" ] || { echo "FATAL: cannot resolve project #$PROJ_NUMBER"; exit 1; }

# 字段 ID 与选项（Status / Priority，按名称匹配）
F_STATUS=$(gql '{"query":"query{node(id:\"'"$PROJ"'\"){... on ProjectV2{fields(first:50){nodes{... on ProjectV2SingleSelectField{name id}}}}}}"}' \
  | jq -r '.data.node.fields.nodes[] | select(.name=="Status") | .id' | head -1)
F_PRIO=$(gql '{"query":"query{node(id:\"'"$PROJ"'\"){... on ProjectV2{fields(first:50){nodes{... on ProjectV2SingleSelectField{name id}}}}}}"}' \
  | jq -r '.data.node.fields.nodes[] | select(.name=="Priority") | .id' | head -1)

declare -A STATUS_OPT PRIO_OPT
while IFS=$'\t' read -r fname fid oname oid; do
  [ -z "$fname" ] && continue
  if [ "$fname" = "Status" ]; then STATUS_OPT[$oname]=$oid; else PRIO_OPT[$oname]=$oid; fi
done < <(gql '{"query":"query{node(id:\"'"$PROJ"'\"){... on ProjectV2{fields(first:50){nodes{... on ProjectV2SingleSelectField{name options{name id}}}}}}}"}' \
  | jq -r '.data.node.fields.nodes[] | select(.name=="Status" or .name=="Priority") | .name as $f | .options[] | [$f, (.id), .name] | @tsv')

declare -A ST=([未开始]="${STATUS_OPT[未开始]}" [进行中]="${STATUS_OPT[进行中]}" [已完成]="${STATUS_OPT[已完成]}")
declare -A PR=([P0]="${PRIO_OPT[P0]}" [P1]="${PRIO_OPT[P1]}" [P2]="${PRIO_OPT[P2]}")

mapfile -t EXIST < <(gql '{"query":"query{node(id:\"'"$PROJ"'\"){... on ProjectV2{items(first:100){nodes{id content{... on DraftIssue{title}}}}}}}"}' \
  | jq -r '.data.node.items.nodes[] | [.id, .content.title] | @tsv')
declare -A IDS=()
for row in "${EXIST[@]}"; do IDS[${row#*$'\t'}]=${row%%$'\t'*}; done

set_field() { # item field option
  gql "$(jq -n --arg p "$PROJ" --arg i "$1" --arg f "$2" --arg o "$3" \
    '{query:"mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}",variables:{p:$p,i:$i,f:$f,o:$o}}')" \
    | jq -r 'if .errors then "ERR " + (.errors[0].message) else "ok" end'
}
create_item() { # title -> item id
  gql "$(jq -n --arg p "$PROJ" --arg t "$1" \
    '{query:"mutation($p:ID!,$t:String!){addProjectV2DraftIssue(input:{projectId:$p,title:$t}){projectItem{id}}}",variables:{p:$p,t:$t}}')" \
    | jq -r 'if .errors then "ERR " + (.errors[0].message) else .data.addProjectV2DraftIssue.projectItem.id end'
}

ok=0; upd=0; fail=0
while IFS=$'\t' read -r title status prio; do
  [ -z "${title:-}" ] && continue
  if [[ -n "${IDS[$title]:-}" ]]; then item=${IDS[$title]}; upd=$((upd+1)); else
    item=$(create_item "$title")
    if [[ "$item" == ERR* ]]; then echo "FAIL create: $title -> $item"; fail=$((fail+1)); continue; fi
  fi
  r=$(set_field "$item" "$F_STATUS" "${ST[$status]}")
  if [[ "$r" != ok ]]; then echo "FAIL status: $title -> $r"; fail=$((fail+1)); continue; fi
  if [[ -n "${prio:-}" && -n "${PR[$prio]:-}" && -n "$F_PRIO" ]]; then
    r=$(set_field "$item" "$F_PRIO" "${PR[$prio]}")
    [[ "$r" != ok ]] && echo "WARN prio: $title -> $r"
  fi
  ok=$((ok+1))
done < "$TSV"
echo "SYNC DONE ok=$ok updated=$upd fail=$fail"
