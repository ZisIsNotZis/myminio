<p align="center">
  <img src="assets/logo.svg" width="112" alt="myminio logo">
</p>

<h1 align="center">myminio</h1>

<p align="center"><strong>一个能看见内部的手写对象存储。</strong></p>

<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>

把一个 blob 拆成分片写进普通目录，再生成一个 XOR 校验分片；保留每个版本，并在下一次读取时重建丢失的分片——约 600 行 Python 和 NumPy。

> **状态：归档，第一代。** 纠删码核心（`ec4.py`）已由 `tests/smoke_ec.py` 验证；外围的 Flask API 只工作了一部分。它**不兼容 S3**，不是生产软件，也不再维护。保留下来，是因为内部足够可读，也作为 `myminio2` 的直接前身。

## 快速开始

真正验证过的是 Python 库本身。它只需要 Python 3 和 NumPy；Flask 只在 HTTP 层用到。

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy flask

mkdir -p dat0 dat1 dat2

python3 - <<'PY'
import numpy as np
from ec4 import EC

ec = EC({f'./dat{i}/': 10**9 for i in range(3)})   # 分片目录 -> 剩余字节数
ec.set('greeting', np.frombuffer(b'hello, shards', 'B'), t=1, chk=1)

print(np.concatenate(ec.get('greeting', chk=1)).tobytes())
# b'hello, shards'
PY
```

`chk=1` 表示 RAID-5：两个数据分片加一个 XOR 校验分片。删掉 `dat0/`–`dat2/` 里的一个数据分片，再用 `chk=1` 读取，分片会被重建并就地写回。

运行验证脚本（只需要 NumPy，使用临时目录）：

```bash
python3 tests/smoke_ec.py
```

启动那个不完整的 HTTP 外壳时，每个参数是“目录/配额字节数”：

```bash
python3 s3svr.py ./dat0/1000000 ./dat1/1000000 ./dat2/1000000
# Flask 监听 http://localhost:5000
```

## 现在能做什么

| 能力 | 位置 |
| --- | --- |
| **RAID-5 XOR 纠删码**——*n* 个数据分片 + 1 个校验分片，可容忍一个分片丢失 | `ec4.split`、`ec4.cat` |
| **RAID-0 条带化**——没有校验（`chk=0`，默认值） | `ec4.split`、`ec4.cat` |
| **带时间戳的版本**与按时间点读取（“早于 *t* 的最新版本”） | `ec4.set`、`ec4.get` |
| **按版本范围删除** | `ec4.rm` |
| **按目录记账配额**，并按剩余空间选择分片落点 | `ec4.EC.__init__`、`ec4.set` |
| **读取时自愈**——重建缺失分片并就地写回 | `ec4.cat` |
| **健康扫描**——遍历所有对象并统计错误 | `ec4.gets` |
| **自定义 Flask API**，刻意不实现 S3 | `s3svr.py` |
| **三节点 MinIO compose 文件**，与 Python 代码互不相关 | `docker-compose.yml` |
| **内存内 XOR 实验**——`ec5.py` 可运行；`ec6.py` 因形状不匹配而崩溃 | `ec5.py`、`ec6.py` |

### HTTP 接口

这只是一层小而不完整的包装，并不是 S3 协议。

| 路由 | 方法 | 实际行为 |
| --- | --- | --- |
| `/obj` | GET | 以 JSON 返回对象键列表 |
| `/obj/<k>` | GET | 以 JSON 返回 `k` 的版本时间戳 |
| `/obj/<k>/<t>` | GET | 返回早于 `t` 的最新版本的字节 |
| `/obj/<k>/<t>` | POST | 把请求体存为版本 `t`（始终是 RAID-0） |
| `/obj/<k>/<t>` | PUT | **坏的**——调用不存在的 `EC.snap`，返回 HTTP 500 |
| `/obj/<k>/<t>` | DELETE | 删除早于 `t` 的版本 |
| `/objs` | GET | **坏的**——返回裸 `int`，返回 HTTP 500 |
| `/ec` | GET | 以 JSON 返回“目录 → 剩余配额” |

没有认证，没有 bucket，没有分片上传，没有 Range GET，没有 ETag，也没有错误映射：对象不存在时返回 HTTP 500，而不是 404。

### 这里没有什么

- **不兼容 S3。** 名字表达的是意图，不是协议实现。
- **没有任何复制。** 唯一的冗余是单校验 XOR，只扛得住一个分片丢失。
- **没有网络分布。** 分片是单进程里的本地文件。把分片放到 HTTP 后端上是 `myminio2` 做的事。
- **没有快照。** 清单里的 `[x] snapshot` 和 `PUT` 路由承诺了一个从未写出的方法。
- **没有打包、配置系统或持续维护的测试。** `tests/smoke_ec.py` 是归档证据，不是 CI。

## 架构

一个对象就是一组分片文件，文件名格式为 `<unix-ts> <data-shards> <index>`，每个分片目录一份：

```text
dat0/greeting/1 2 0   # 数据分片 0
dat1/greeting/1 2 1   # 数据分片 1
dat2/greeting/1 2 2   # XOR 校验分片
```

**写入路径。** 先把载荷补齐到整数个分片，切成 *n* 个数据分片；`chk=1` 时把这些分片 XOR 成一个校验分片；按剩余配额给目录排序，然后每个目录写一个分片并扣减配额。

**读取路径。** 选出早于目标时间戳的最新版本，按索引加载分片；缺失的分片由其余数据分片加校验分片重建，并写回磁盘；最后拼接数据分片。`chk=0` 时没有校验分片，也就无法修复。

分片目录就是普通本地目录，用 `ls`、`sha1sum` 和文本编辑器就能看清全部内容——这正是它的意义。

### 独立的 MinIO 集群

`docker-compose.yml` 用来启动官方 MinIO，**和 Python 代码没有关系**。它需要从环境变量读取 root 凭据；分布式 MinIO 通常至少需要四块盘，所以这个三节点布局可能在启动时被拒绝；注释掉的 `minio3`/`minio4` 可以恢复这套命令原本面向的五节点布局。

```bash
export MINIO_ROOT_USER=myminio
export MINIO_ROOT_PASSWORD=replace-with-a-real-value
mkdir -p dat0 dat1 dat2
docker compose up -d        # S3 API 在 :9000、:9002、:9004
```

### 仓库结构

| 路径 | 行数 | 内容 |
| --- | ---: | --- |
| [`ec.py`](ec.py) | 69 | 第一版：`EC(list)`、XOR 校验、`write/read/list/remove` |
| [`ec2.py`](ec2.py) | 139 | 加入 `split_xor`/`xor` 辅助函数和时间戳版本 |
| [`ec3.py`](ec3.py) | 92 | 改为 `EC(dict)`（目录 → 剩余字节），并按配额选择落点 |
| [`ec4.py`](ec4.py) | 148 | 成熟版本：RAID-5 + RAID-0、版本、配额、健康扫描、错误计数 |
| [`ec5.py`](ec5.py) | 47 | 数组级的内存 XOR 实验（import 时即运行） |
| [`ec6.py`](ec6.py) | 41 | `ec5.py` 的变体，因形状不匹配而崩溃 |
| [`s3svr.py`](s3svr.py) | 55 | 包在 `ec4` 外面的 Flask `/obj` 接口 |
| [`vector.py`](vector.py) | 34 | 草稿：可增长的 `mmap` 数组，在当前 NumPy 上崩溃 |
| [`docker-compose.yml`](docker-compose.yml) | 70 | 三节点官方 MinIO 集群（已修复 YAML） |
| [`tests/smoke_ec.py`](tests/smoke_ec.py) | 117 | 对上文 `ec4` 各项声明的归档验证 |
| [`docs/project-status.md`](docs/project-status.md) | — | 分类、证据与边界 |

## 如何开发

没有构建步骤，也没有需要安装的包。核心只需要 NumPy，`s3svr.py` 才需要 Flask。

```bash
pip install numpy flask     # 在 virtualenv 里
python3 tests/smoke_ec.py   # 覆盖 RAID-5、RAID-0、版本、修复和分片不一致检测
```

代码像一架梯子：每个 `ec*.py` 都是同一个想法的一个自包含阶段。改动核心时，保持 `ec4.py` 可运行，并重跑冒烟检查。`vector.py`、`ec5.py`、`ec6.py` 是草稿实验，不在可运行路径上。

## 如何贡献

这是一个归档仓库，不是活跃维护的项目，因此功能型 PR 大概率不会被合并。文档更正、归档证据补充，或者在新版 NumPy 上复现失败，都欢迎提 issue。想继续推进这个想法，请看 `myminio2`。

## 路线图

### 已实现

- XOR 纠删码：RAID-5（一个校验分片）和 RAID-0（仅条带化）。
- 版本历史、按时间点读取、按版本范围删除。
- 按目录的配额记账，以及按配额选择写入位置。
- 读取时重建并就地修复，以及分片不一致检测。
- 全局健康扫描与错误计数。
- 内存内 XOR 实验，以及一个不完整的 Flask API。
- 一个修好 YAML 的三节点 MinIO compose 文件，用作对照。

### 计划中（不在本归档内）

- 补上缺失的 `EC.snap` 和 `EC.ln`，或者删掉承诺它们的路由和清单项。
- 让 HTTP 层返回真实状态码（缺失对象 404、错误时间戳 400），并让 `/objs` 返回 JSON。
- 在 `POST /obj/<k>/<t>` 上暴露 `chk`，让 API 真正能写 RAID-5。
- 用一个小而持续维护的测试套件和包结构取代草稿实验。
- 把分片放到 HTTP 后端后面——这件事已经在 `myminio2` 里完成。

### 未来设想

`myminio` 是一架学习用的梯子：它有足够的对象存储骨架，让纠删码、版本、落点选择和修复都变得具体，同时不把任何东西藏在框架后面。下一代已经存在于 `myminio2`：同样的分片/校验思路被拆到了多个 HTTP 后端上。如果重新捡起这份代码，有用的方向是正确性和可观测性——一个不说谎的 HTTP 层、一套真正的测试、分片在网络上的迁移——而不是追求 S3 功能对齐。

## 许可证

GNU Affero General Public License v3.0 only。见 [`LICENSE`](LICENSE)。
