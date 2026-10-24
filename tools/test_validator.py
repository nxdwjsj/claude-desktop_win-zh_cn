import importlib.util as u
import sys

spec = u.spec_from_file_location('v', r'D:\Project\DeepSeek\out\zh-work\validate_structure.py')
v = u.module_from_spec(spec)
spec.loader.exec_module(v)

fails = []


def expect(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)


# ---- 漏检回归：select 自定义分支键 ----
SEL = '{has, select, both {Artifact by {author}, updated {time}} author {X} other {Y}}'
SEL_BROKEN = '{has, select, both {工件} other {工件}}'
errs = v.check(SEL, SEL_BROKEN)
expect('select 丢分支 -> 必须报错', len(errs) > 0)
print('      errors:', errs)

# ---- 误报回归：单词里含 one/other，无 ICU ----
expect('Pre-clone {repo} 无 ICU -> 不报错',
       v.check('Pre-clone {repo} at session start', '在会话启动时预克隆 {repo}') == [])
expect('clone {repo} -> 不报错',
       v.check('clone {repo}', '克隆 {repo}') == [])
expect('someone {x} -> 不报错',
       v.check('Ask someone {x} to help', '请某人 {x} 帮忙') == [])
expect('another {x} -> 不报错',
       v.check('another {x}', '另一个 {x}') == [])

# ---- 误报回归：正文里的 , date, / , number, ----
expect('vendor, date, amount 无 ICU -> 不报错',
       v.check('a simple expense table: vendor, date, amount. Flag anything',
               '一个简单的开支表：供应商、日期、金额。标记任何内容') == [])
expect(', number, 正文 -> 不报错',
       v.check('Set the number, count, total values', '设置数值、计数、合计') == [])

# ---- 正常 ICU 仍要能校验 ----
expect('plural 结构一致 -> 不报错',
       v.check('{count, plural, one {# file} other {# files}}',
               '{count, plural, one {# 个文件} other {# 个文件}}') == [])
expect('plural 丢分支 -> 报错',
       v.check('{count, plural, one {# file} other {# files}}',
               '{count, plural, other {# 个文件}}') != [])
expect('plural 多加 # -> 报错',
       v.check('Hide {count, plural, one {skipped check} other {skipped checks}}',
               '隐藏 {count, plural, one {# 项已跳过的检查} other {# 项}}') != [])
expect('select 正常 -> 不报错',
       v.check('{action, select, connect {Connect} other {Confirm}}',
               '{action, select, connect {连接} other {确认}}') == [])

# ---- 变量丢失 / 新增 ----
expect('丢普通变量 -> 报错', v.check('Hello {name}', '你好') != [])
expect('凭空多变量 -> 报错', v.check('Hello {name}', '你好 {other}') != [])
expect('{does} 丢失 -> 报错',
       v.check("This Artifact {does}, so it can't be shared.", '此工件，因此无法公开分享。') != [])

# ---- 嵌套 ICU ----
expect('嵌套 ICU 结构一致 -> 不报错',
       v.check('{n, plural, one {{x, number} item} other {{x, number} items}}',
               '{n, plural, one {{x, number} 项} other {{x, number} 项}}') == [])

# ---- 标签 ----
expect('HTML 标签丢失 -> 报错', v.check('<b>bold</b>', '粗体') != [])
expect('HTML 标签保留 -> 不报错', v.check('<b>bold</b>', '<b>粗体</b>') == [])

print()
print('RESULT:', 'ALL PASS' if not fails else 'FAILURES: %s' % fails)
sys.exit(1 if fails else 0)
