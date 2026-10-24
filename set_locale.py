import io
import json
import os
import shutil

# 把 Claude 实际读取的 config.json 的 locale 设为 zh-CN。
# 注意：本项目补丁默认写 %APPDATA%\Claude-3p\config.json，
# 但本机 3p 部署（deploymentMode=3p）实际读取的是 %LOCALAPPDATA%\Claude-3p\config.json。
paths = [
    os.path.join(os.environ['LOCALAPPDATA'], 'Claude-3p', 'config.json'),
]

for p in paths:
    if not os.path.exists(p):
        print('SKIP (not found):', p)
        continue
    shutil.copy2(p, p + '.zh-cn-backup')
    data = json.loads(io.open(p, encoding='utf-8').read())
    old = data.get('locale')
    data['locale'] = 'zh-CN'
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent='\t')
        f.write('\n')
    print('OK %s: locale %r -> zh-CN (backup: %s.zh-cn-backup)' % (p, old, os.path.basename(p)))
