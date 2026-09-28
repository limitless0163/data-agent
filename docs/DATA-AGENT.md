# 掌柜问数

作者：limitless

## 1 项目概述

掌柜问数是一个基于自然语言处理与数据分析技术的智能数据服务系统，面向数据仓库应用场景，旨在帮助用户通过对话方式高效获取数据仓库中的数据洞察。用户无需掌握复杂的查询语法，即可用自然语言提出问题，系统根据元数据生成并执行 SQL，实时显示执行进度，并将查询结果以表格形式展示。

## 2 项目架构

### 2.1 概述

本项目以数据仓库的元数据为核心，使用 MySQL 存储结构化元数据信息，结合 Qdrant 构建语义向量索引、Elasticsearch 构建全文索引，形成统一的元数据知识库。查询过程中，系统首先根据用户自然语言问题进行多路召回，筛选相关表、字段及指标定义，再将元数据信息与用户问题共同输入大模型生成 SQL，最终完成自动查询与结果返回。

### 2.2 元数据知识库

元数据知识库作为数据仓库的语义基础设施，用于集中管理和高效检索表结构、字段定义、字段取值示例及复杂指标说明等元数据信息，支撑后续的 SQL 生成。

完整的元数据统一存储于 MySQL 数据库中，并对其中部分关键信息构建向量索引和全文索引，以提升语义召回与关键词召回的效果。

#### 2.2.1 元数据库

元数据库共有四张表，用于存储完整的元数据信息，包括数据仓库的表格信息、字段信息和指标信息。

- table_info：保存表编号、表名称、表类型和表描述，表类型区分事实表与维度表。
- column_info：保存字段编号、名称、数据类型、字段角色、数据示例、业务描述、别名和所属表编号，字段角色包括主键、外键、度量和维度。
- metric_info：保存指标编号、名称、业务描述、关联字段和别名。
- column_metric：保存字段与指标的关联关系，由字段编号和指标编号共同标识。

#### 2.2.2 向量索引

向量索引主要用于对 column_info（字段信息）和 metric_info（指标信息）进行语义召回。

字段信息的向量索引分别对字段名称、业务描述和各个别名进行向量化，每个向量点同时保存对应字段的完整业务信息。

指标信息的向量索引分别对指标名称、业务描述和各个别名进行向量化，每个向量点同时保存对应指标的完整业务信息。

通过这些向量表示，系统能够根据用户问题及其相关关键词检索语义相近的字段和指标。

#### 2.2.3 全文索引

全文索引主要用于对字段取值进行检索与匹配，建立全文索引的主要是数据仓库中各种维度表的维度字段。

索引记录包含取值编号、具体取值和所属字段编号。取值内容采用文本索引，使用 standard 分词器；编号和所属字段编号采用精确匹配类型。

### 2.3 问数智能体

问数智能体主要基于 LangGraph 进行开发。用户问题进入工作流后，先抽取关键词，再分别召回字段信息、指标信息和字段取值。召回结果合并后，筛选相关表、字段和指标，补充日期及数据库环境信息，交由大模型生成 SQL。

生成的 SQL 经过验证后进入执行阶段；验证失败时，先由大模型根据错误信息进行校正，再执行校正后的 SQL。工作流在执行过程中实时输出进度，查询完成后返回结果。

## 3 项目开发环境

### 3.1 创建项目

后端使用 uv 进行依赖管理与虚拟环境管理，依赖声明与锁文件位于 backend 目录。

### 3.2 安装依赖

后端依赖由 backend/pyproject.toml 声明，通过 uv 锁文件管理，主要依赖说明如下：

- fastapi[standard]：高性能异步 Web 框架，作为整个服务的 API 入口。
- sqlalchemy[asyncio]：ORM 与异步数据库访问组件，用统一模型管理数据库读写与事务。
- asyncmy：MySQL 的高性能 asyncio 驱动，配合 SQLAlchemy 实现全异步数据库访问。
- qdrant-client：向量数据库客户端，用于 Embedding 向量存储与相似度检索。
- elasticsearch[async]：异步 Elasticsearch 客户端，用于全文检索；依赖范围为 8.x。
- langchain：LLM 应用编排框架，用于提示词与模型调用链路。
- langchain-deepseek：DeepSeek 模型集成依赖。
- langchain-huggingface：连接 HuggingFace Embedding 服务。
- huggingface-hub：HuggingFace 服务相关依赖。
- python-dotenv：加载项目根目录的环境变量文件。
- langgraph：用图结构构建可控 Agent 流程。
- jieba：中文分词库。
- omegaconf：分层配置系统，适合多环境、多模型、多参数管理。
- pyyaml：用于 YAML 导入导出。
- loguru：日志库，替代 logging，适合工程化项目。
- cryptography：加密与证书基础库，很多网络、数据库和安全库的底层依赖。

### 3.3 安装所需服务

#### 3.3.1 概述

本项目所需的全部服务如下：

- MySQL：用于存储数据仓库的元数据信息，包括表格信息、字段信息和指标信息，同时保存模拟数据仓库的业务数据。
- Qdrant：作为向量数据库，用于存储字段信息、指标信息的向量表示，在用户提问时通过语义相似度检索出最相关的元数据，为生成 SQL 提供高相关性的上下文信息。
- Elasticsearch：对各维度字段的实际取值建立倒排索引。当用户问题中包含自然语言形式的维度描述时，例如“华北地区”“数码品类”，可通过全文检索匹配到数据库中真实存在的字段取值，为生成 SQL 时的 WHERE 条件或者 GROUP BY 分组提供准确依据。
- Text Embedding Inference：用于部署 Embedding 模型推理服务，将元数据文本及用户问题转换为向量表示，为 Qdrant 提供向量数据来源，是语义检索能力的基础。

#### 3.3.2 安装

基础服务由根目录 docker-compose.yml 定义，通过 Makefile 启动开发或生产环境。首次启动时，knowledge-init 等待数据库、全文检索、向量库和 Embedding 服务就绪并构建知识库；后端在 MySQL 健康且知识库初始化成功后启动。

## 4 基础设施搭建

### 4.1 项目目录结构

项目各部分的职责如下：

- backend：FastAPI 后端、问数智能体、元数据知识库构建逻辑及后端测试。
- backend/app/agent：工作流、状态、运行上下文、大模型客户端、执行节点及 Markdown 提示词。
- backend/app/api：查询路由。
- backend/app/dependencies：接口依赖注入。
- backend/app/schemas：接口请求结构。
- backend/app/core：配置、Embedding 客户端、生命周期、日志和请求上下文。
- backend/app/db：MySQL、Qdrant 和 Elasticsearch 客户端管理。
- backend/app/models：元数据库 ORM 实体。
- backend/app/entities：业务实体。
- backend/app/repositories：各存储系统的读写操作与实体映射。
- backend/app/services：查询服务和元数据知识库构建服务。
- backend/scripts：知识库构建及依赖就绪等待脚本。
- frontend：Next.js 前端，包含聊天页面、SSE 服务、后端代理、样式和前端测试。
- infra/docker/mysql：数据库初始化结构与种子数据。
- scripts：跨服务 HTTP 检查脚本。
- tests/e2e：前后端浏览器测试。
- docs：项目文档。

根目录的 docker-compose.yml 定义服务，Makefile 提供统一的编排与测试入口。

### 4.2 配置参数管理

#### 4.2.1 配置文件

本项目采用 YAML 文件管理配置参数，配置文件路径为 backend/app/core/config/app_config.yaml。配置内容包括日志、元数据库、模拟数据仓库、Qdrant、Embedding、Elasticsearch 和大模型的相关参数。数据库密码与模型 API 密钥可通过项目根目录的 .env 文件或环境变量提供。

日志配置分为文件输出和控制台输出。文件输出配置包含是否启用、日志级别、保存目录、轮转大小和保留时间；控制台输出配置包含是否启用及日志级别。默认两种输出均启用，级别均为 INFO；文件保存在后端运行目录下的 logs 目录，达到 10 MB 时轮转，保留 7 天。

MySQL 配置分别面向 meta 元数据库和 dw 模拟数据仓库，包含主机、端口、用户名、密码和数据库名称。YAML 默认连接本机的 3306 端口；Compose 中连接 mysql 服务的 3306 端口，主机映射端口为 3307。

Qdrant 配置包含主机、端口和向量维度。YAML 默认连接本机的 6333 端口，向量维度为 1024；Compose 中连接 qdrant 服务。

Embedding 配置包含主机、端口和模型名称。YAML 默认连接本机的 8081 端口，模型为 BAAI/bge-large-zh-v1.5；Compose 中连接 embeddings 服务的 80 端口。

Elasticsearch 配置包含主机、端口和索引名称。YAML 默认连接本机的 9200 端口；Compose 中连接 elasticsearch 服务，取值索引由 Repository 定义。

#### 4.2.2 加载工具

本项目使用 OmegaConf 加载 YAML 配置文件，具体用法可参考其官网。

配置读取逻辑放置在 backend/app/core/config/app_config.py 中。通过数据类分别定义文件日志、控制台日志、数据库、Qdrant、Embedding、Elasticsearch 和大模型的配置结构，再组合为应用配置。加载时，读取项目根目录的 .env 文件和 YAML 默认值，以已有环境变量覆盖运行时配置，再与结构化配置合并，转换为应用配置对象。

### 4.3 MySQL 客户端管理

本项目中的 MySQL 客户端使用 SQLAlchemy，具体用法可参考官方文档。客户端管理逻辑位于 backend/app/db/mysql_client_manager.py。

客户端管理器根据数据库配置构建连接地址，使用 asyncmy 驱动和 UTF-8 字符集，初始化异步数据库引擎与会话工厂。连接池大小为 10，并启用连接可用性检查。会话支持自动刷新和自动开启事务，提交后不使对象过期。关闭时释放数据库引擎资源。

项目分别创建面向 dw 数据仓库和 meta 元数据库的客户端管理器。

此外，在 backend/app/models 包下定义 meta 数据库各表的 ORM 实体类：

- base.py：定义各 ORM 实体共同使用的声明式基类。
- table_info_mysql.py：定义表信息实体，包含表编号、名称、类型和描述。
- column_info_mysql.py：定义字段信息实体，包含字段编号、名称、数据类型、角色、数据示例、描述、别名和所属表编号；数据示例与别名使用 JSON 类型保存。
- metric_info_mysql.py：定义指标信息实体，包含指标编号、名称、描述、关联字段和别名；关联字段与别名使用 JSON 类型保存。
- column_metric_mysql.py：定义字段与指标关系实体，以字段编号和指标编号作为联合主键。

### 4.4 Qdrant 客户端管理

本项目中的 Qdrant 客户端使用 qdrant-client，具体用法可参考官方文档。客户端管理逻辑位于 backend/app/db/qdrant_client_manager.py。

管理器根据主机和端口创建异步 Qdrant 客户端，并提供初始化和关闭操作。

### 4.5 ES 客户端管理

本项目中的 ES 客户端使用 elasticsearch，具体用法可参考官方文档。客户端管理逻辑位于 backend/app/db/es_client_manager.py。

管理器根据主机和端口创建异步 Elasticsearch 客户端，并提供初始化和关闭操作。

### 4.6 Embedding 客户端管理

本项目中的 Text Embedding Inference 客户端使用 HuggingFaceEndpointEmbeddings，具体用法可参考官方文档。客户端管理逻辑位于 backend/app/core/clients/embedding_client_manager.py。

管理器根据配置中的主机和端口确定 Embedding 服务地址，初始化 HuggingFaceEndpointEmbeddings 客户端，供元数据向量化及用户问题向量化使用。

### 4.7 日志管理

本项目使用 loguru 管理日志，具体用法可参考其官网。日志管理逻辑位于 backend/app/core/log.py，统一控制日志输出。

日志格式包含时间、级别、request_id、模块名称、函数名称、行号和消息内容。系统根据配置分别启用控制台输出及文件输出；文件日志保存为 app.log，使用 UTF-8 编码，并按照配置执行轮转与保留策略。Compose 使用 backend_logs 数据卷保存文件日志。

## 5 元数据知识库

### 5.1 需求说明

本章旨在开发一个用于构建元数据知识库的脚本。该脚本以一个 YAML 配置文件作为输入参数，配置文件中定义了需要同步至元数据知识库的表格信息与指标信息。脚本功能包括：

- 根据配置内容，将指定的表格及指标信息同步至 Meta 数据库。
- 为字段信息和指标信息构建向量索引。
- 为字段取值建立全文索引。

### 5.2 代码组织规划

构建元数据知识库模块采用分层设计，各部分职责如下：

- backend/app/core/config/meta_config.yaml：指定待同步的表格和指标。
- backend/app/core/config/meta_config.py：定义元数据配置参数的结构。
- backend/scripts/build_meta_knowledge.py：构建元数据知识库的入口脚本，负责解析命令行参数。
- backend/scripts/wait_and_build_meta.py：等待基础服务及数据仓库种子数据就绪，再调用构建脚本。
- backend/app/services/meta_knowledge_service.py：实现知识库构建的核心业务逻辑。
- backend/app/entities：定义表信息、字段信息、指标信息、字段与指标关系、字段取值等业务实体。
- backend/app/repositories/mysql/meta：实现元数据库读写操作，mappers 子目录负责 ORM 实体与业务实体之间的类型转换。
- backend/app/repositories/mysql/dw：实现数据仓库访问。
- backend/app/repositories/qdrant：实现字段和指标向量集合的读写操作。
- backend/app/repositories/es：实现字段取值全文索引的读写操作。

### 5.3 具体实现

#### 5.3.1 配置文件

##### 结构说明

配置文件采用 YAML 格式，用于指定待同步的表格和指标信息，分为表格信息与指标信息两部分。

表格信息包含真实表名、表角色、表的业务含义说明和字段列表。表角色分为维度表与事实表。每个字段需要说明真实字段名、字段角色、业务含义、同义词，以及该字段取值是否需要同步到 Elasticsearch 建立全文索引。字段角色包括主键、外键、维度和度量。

指标信息包含指标名称、业务含义与计算口径说明、相关字段和同义词。相关字段采用表名与字段名组合的方式标识。

##### 具体配置

元数据配置定义了 dw 数据仓库中的 5 张表和 2 个指标。

**地区维度表 dim_region**

用于描述订单发生的地理区域信息，各字段说明如下：

- region_id：地区唯一标识，角色为主键，别名为“地区ID”“区域ID”，不向全文索引同步取值。
- province：订单所属的省份名称，角色为维度，别名为“省份”“省”“所在省份”，同步取值。
- region_name：订单所属的大区名称，如华东、华南等，角色为维度，别名为“地区”“区域”“大区”，同步取值。
- country：地区所属国家名称，角色为维度，别名为“国家”“国家名称”，同步取值。

**客户维度表 dim_customer**

用于描述下单客户的基本属性，各字段说明如下：

- customer_id：客户唯一标识，角色为主键，别名为“客户ID”“用户ID”，不向全文索引同步取值。
- customer_name：客户名称，角色为维度，别名为“客户名称”“用户名称”，同步取值。
- gender：客户性别，角色为维度，别名为“性别”，同步取值。
- member_level：客户会员等级，角色为维度，别名为“会员等级”“用户等级”，同步取值。

**商品维度表 dim_product**

用于描述商品的基本属性信息，各字段说明如下：

- product_id：商品唯一标识，角色为主键，别名为“商品ID”“产品ID”，不向全文索引同步取值。
- product_name：商品名称，角色为维度，别名为“商品名称”“产品名称”，同步取值。
- category：商品所属品类，角色为维度，别名为“商品类别”“品类”“分类”，同步取值。
- brand：商品品牌名称，角色为维度，别名为“品牌”“品牌名称”，同步取值。

**时间维度表 dim_date**

用于多时间粒度分析，各字段说明如下：

- date_id：日期唯一标识，格式为 yyyyMMdd，角色为主键，别名为“日期ID”“日期”，不向全文索引同步取值。
- year：年份，角色为维度，别名为“年”“年份”，不向全文索引同步取值。
- quarter：季度，角色为维度，别名为“季度”，同步取值。
- month：月份，角色为维度，别名为“月”“月份”，不向全文索引同步取值。
- day：日，角色为维度，别名为“日”“天”，不向全文索引同步取值。

**订单事实表 fact_order**

用于记录订单数量和金额等核心指标，各字段说明如下：

- order_id：订单唯一标识，角色为主键，别名为“订单ID”。
- customer_id：关联客户维度的外键，别名为“客户ID”“用户ID”。
- product_id：关联商品维度的外键，别名为“商品ID”“产品ID”。
- date_id：关联时间维度的外键，别名为“日期”“下单日期”。
- region_id：关联地区维度的外键，别名为“地区ID”“区域ID”。
- order_quantity：订单中商品的购买数量，角色为度量，别名为“销量”“购买数量”“件数”。
- order_amount：订单金额，角色为度量，别名为“销售额”“订单金额”“收入”。

订单事实表的上述字段均不向全文索引同步取值。

**指标信息**

- GMV：全称 Gross Merchandise Value，表示所有订单的成交金额总和；关联字段为 fact_order.order_amount，别名为“成交总额”“订单总额”。
- AOV：全称 Average Order Value，表示所有订单的成交金额平均值；配置中的关联字段为 fact_order.order_quantity，别名为“平均单价”“平均订单金额”。

##### 结构定义

在 backend/app/core/config/meta_config.py 中定义上述配置参数的结构。字段配置包含名称、角色、描述、别名和取值同步标记；表格配置包含名称、角色、描述和字段配置列表；指标配置包含名称、描述、关联字段和别名。顶层元数据配置由可选的表格列表与指标列表组成。

#### 5.3.2 入口脚本

入口脚本位于 backend/scripts/build_meta_knowledge.py，主要负责解析调用者传入的配置文件路径。

脚本初始化元数据库、数据仓库、Qdrant、Embedding 和 Elasticsearch 客户端，创建元数据库与数据仓库会话，组装各存储系统的 Repository 及 Embedding 客户端，构建元数据知识库服务并调用其构建功能。执行完成后，关闭元数据库、数据仓库、Qdrant 和 Elasticsearch 客户端。

#### 5.3.3 核心业务逻辑

核心业务逻辑位于 backend/app/services/meta_knowledge_service.py，由 MetaKnowledgeService 组织元数据同步与索引构建过程。

**加载配置文件**

使用 OmegaConf 读取调用方指定的 YAML 文件，与元数据配置结构合并，转换为配置对象。

**保存表格与字段信息**

根据配置构造表信息，以表名作为表编号。然后查询数据仓库中各字段的真实数据类型，并为每个字段读取最多 10 个不同取值作为示例。

字段编号由表名与字段名组成，字段信息还包含名称、数据类型、角色、取值示例、业务描述、别名和所属表编号。表信息与字段信息在同一个元数据库事务中保存。

**构建字段向量索引**

确保字段向量集合存在，分别将字段名称、描述和各个别名作为待向量化文本，为每段文本生成唯一的向量点编号，并附带完整字段信息。

待向量化文本按每批 10 条调用 Embedding 服务，得到向量后，将编号、向量及字段信息写入 Qdrant。

**构建字段取值全文索引**

确保 Elasticsearch 取值索引存在，根据各字段的同步标记，选择需要建立全文索引的字段。对这些字段从数据仓库读取不同取值，读取上限为 100000 条。

每条取值记录包含由字段编号与取值组成的编号、具体取值及所属字段编号，随后批量写入 Elasticsearch。

**保存指标与字段关联关系**

根据配置构造指标信息，以指标名称作为指标编号。针对每个指标的关联字段，创建字段与指标的关系记录。指标信息和关联关系在同一个元数据库事务中保存。

**构建指标向量索引**

确保指标向量集合存在，分别将指标名称、描述和各个别名转换为向量。每个向量点具有唯一编号，并附带完整指标信息；向量化同样按每批 10 条进行，最后写入 Qdrant。

构建流程先处理表格信息，包括保存元数据、建立字段向量索引和取值全文索引，再处理指标信息，包括保存指标及关系、建立指标向量索引。表格或指标配置未提供时，跳过对应部分。各阶段均记录日志，全部执行完毕后记录知识库构建完成。

#### 5.3.4 数据读写操作

##### 业务实体类

业务实体类用于统一封装不同存储系统中的数据结构，如 Meta 数据库、Elasticsearch、Qdrant，作为应用上层组件进行读写操作时的标准参数类型和返回值类型。本项目定义以下业务实体：

- TableInfo：表信息，包含编号、名称、角色和描述，定义于 backend/app/entities/table_info.py。
- ColumnInfo：字段信息，包含编号、名称、数据类型、角色、示例取值、描述、别名和所属表编号，定义于 backend/app/entities/column_info.py。
- MetricInfo：指标信息，包含编号、名称、描述、关联字段和别名，定义于 backend/app/entities/metric_info.py。
- ColumnMetric：字段与指标关系，包含字段编号和指标编号，定义于 backend/app/entities/column_metric.py。
- ValueInfo：字段取值信息，包含编号、具体取值和所属字段编号，定义于 backend/app/entities/value_info.py。

##### meta_mysql_repository

meta_mysql_repository 用于实现 meta 数据库的读写操作，位于 backend/app/repositories/mysql/meta/meta_mysql_repository.py。

**类型映射**

在 backend/app/repositories/mysql/meta/mappers 包下定义 Mapper 类，用于 SQLAlchemy 实体类与对应的业务实体类之间的类型转换。

- TableInfoMapper：表信息的双向转换，位于 table_info_mapper.py。
- ColumnInfoMapper：字段信息的双向转换，位于 column_info_mapper.py。
- MetricInfoMapper：指标信息的双向转换，位于 metric_info_mapper.py。
- ColumnMetricMapper：字段与指标关系的双向转换，位于 column_metric_mapper.py。

**读写操作**

Repository 接收异步数据库会话，将表信息、字段信息、指标信息和字段与指标关系转换为对应 ORM 实体，再批量加入会话，由业务服务控制事务。

##### dw_mysql_repository

dw_mysql_repository 用于实现模拟数据仓库（dw 库）的读写操作，位于 backend/app/repositories/mysql/dw/dw_mysql_repository.py。

构建知识库时，主要提供两项能力：查询指定表的字段名称及数据类型，以及按指定上限查询某字段的不同取值。

##### column_qdrant_repository

column_qdrant_repository 用于实现 Qdrant 中字段信息集合的读写操作，位于 backend/app/repositories/qdrant/column_qdrant_repository.py。

写入前检查集合是否存在，不存在时按配置中的向量维度创建集合，采用余弦相似度。写入操作将编号、向量和字段业务信息组合为向量点，默认每批写入 20 条。

##### metric_qdrant_repository

metric_qdrant_repository 用于实现 Qdrant 中指标信息集合的读写操作，位于 backend/app/repositories/qdrant/metric_qdrant_repository.py。

该层负责指标向量集合的准备及批量写入，为后续指标语义召回提供存储访问能力。

##### value_es_repository

value_es_repository 用于实现 Elasticsearch 中字段取值索引的读写操作，位于 backend/app/repositories/es/value_es_repository.py。

取值索引名称为 data-agent-value，关闭动态字段映射。取值编号与所属字段编号采用 keyword 类型；具体取值采用 text 类型，索引和检索时均使用 standard 分词器。

写入前检查索引是否存在，不存在时创建索引及映射；取值信息默认每批 20 条通过批量接口写入。

### 5.4 测试

在终端运行构建入口脚本，并传入元数据配置文件路径。执行完毕后，可查看 meta 数据库、Elasticsearch 和 Qdrant 中是否有数据写入。

## 6 问数智能体

### 6.1 需求说明

本章旨在实现问数智能体的工作流，工作流的编排以及各节点的职责可参考前文 2.3 节。为保证前端有较好的用户体验，工作流需要实时输出执行进度和查询结果。

工作流的流式输出可参考 LangGraph 官网。本项目与前端约定三类消息：执行进度、查询结果和错误信息。

**执行进度**

消息类型为 progress，step 表示当前执行步骤，例如“召回字段”；status 表示节点状态：running 表示节点开始执行，success 表示执行成功，error 表示执行失败。

**查询结果**

消息类型为 result，data 保存结果记录列表，每条记录包含查询返回的字段及其值。

**错误信息**

消息类型为 error，message 保存执行过程中产生的错误说明。

### 6.2 代码组织规划

问数智能体的核心逻辑主要位于 backend/app/agent 目录下，包括工作流定义、状态定义、运行上下文、大模型定义和各个执行节点。

在智能体执行过程中，部分节点需要访问元数据或向量、检索系统以获取辅助信息，相关的查询与访问逻辑统一封装在 backend/app/repositories 目录中，供各个 Agent 节点按需调用。

除程序逻辑外，智能体运行还高度依赖提示词（Prompt）。所有提示词均集中管理在 backend/app/agent/prompts 目录下，包括字段召回关键词扩展、指标召回关键词扩展、字段取值召回关键词扩展、表格信息过滤、指标信息过滤、SQL 生成和 SQL 校正等提示词。

### 6.3 具体实现

#### 6.3.1 prompts

##### 提示词

提示词保存在 backend/app/agent/prompts 目录，分别用于关键词扩展、表格与指标筛选、SQL 生成及校正。

##### 提示词加载

提示词加载工具根据传入的名称定位对应的 .md 文件，以 UTF-8 编码读取并返回提示词文本。加载逻辑位于 backend/app/agent/prompt_loader.py。

#### 6.3.2 llm

在 backend/app/agent/llm.py 中统一定义大模型。首次调用时读取配置中的模型名称、API 密钥和接口基础地址创建客户端，温度参数设置为 0，并缓存客户端供各节点复用。

#### 6.3.3 state

在 backend/app/agent/state.py 中定义智能体状态，用于在节点之间传递用户问题、中间结果和执行信息。

表格状态包含表名称、角色、描述及字段列表；字段状态包含名称、数据类型、角色、示例取值、描述和别名；指标状态包含名称、描述、关联字段及别名。日期状态包含当前日期、星期和季度，数据库状态包含数据库方言与版本。

智能体整体状态包括：

- 用户查询及其关键词。
- 召回的字段信息、字段取值和指标信息。
- 合并及筛选后的表信息和指标信息。
- 日期信息和数据库环境信息。
- 生成的 SQL。
- SQL 验证时的错误信息。

#### 6.3.4 context

在 backend/app/agent/context.py 中定义智能体运行时所需的上下文依赖，包括 Embedding 客户端、字段向量 Repository、指标向量 Repository、字段取值 Elasticsearch Repository、元数据库 Repository 和数据仓库 Repository。

#### 6.3.5 nodes

##### extract_keywords

关键词抽取节点位于 backend/app/agent/nodes/extract_keywords.py。

节点读取用户查询，使用 jieba 抽取指定词性的关键词，包括名词、人名、地名、机构团体名、其他专有名词、动词、名动词、形容词、名形词、英文、成语和常用固定短语。随后将完整用户查询也加入关键词列表，去重后写回智能体状态。

节点在开始和完成时输出“抽取关键字”的进度消息，并记录抽取结果。

##### recall_column

字段召回节点位于 backend/app/agent/nodes/recall_column.py。

节点先利用大模型和字段召回关键词扩展提示词，根据用户问题生成扩展关键词，将模型结果与已有关键词合并去重。随后逐个调用 Embedding 服务生成查询向量，通过字段向量 Repository 检索字段信息，并按字段编号去重，得到最终召回字段列表。

backend/app/repositories/qdrant/column_qdrant_repository.py 提供向量查询能力，默认相似度阈值为 0.6，每次最多返回 5 条结果，并将向量点附带的数据转换为字段业务实体。

节点输出“召回字段”的执行进度；失败时输出错误状态、记录错误并继续抛出异常。

##### recall_metric

指标召回节点位于 backend/app/agent/nodes/recall_metric.py。

节点利用大模型和指标召回关键词扩展提示词生成扩展关键词，与已有关键词合并去重。随后将关键词转换为查询向量，通过指标向量 Repository 检索指标信息，并按指标编号去重。

backend/app/repositories/qdrant/metric_qdrant_repository.py 提供向量查询能力，默认相似度阈值为 0.6，每次最多返回 5 条结果，并将返回数据转换为指标业务实体。

节点输出“召回指标”的执行进度；失败时输出错误状态、记录错误并抛出异常。

##### recall_value

字段取值召回节点位于 backend/app/agent/nodes/recall_value.py。

节点利用大模型和字段取值召回关键词扩展提示词生成扩展关键词，与已有关键词合并去重。随后逐个关键词调用 Elasticsearch 取值检索，按取值记录编号去重，形成最终召回取值列表。

backend/app/repositories/es/value_es_repository.py 提供全文检索能力，通过具体取值的文本匹配召回记录，默认最低评分为 0.6，每次最多返回 5 条结果，并将返回数据转换为取值业务实体。

节点输出“召回字段取值”的执行进度；失败时输出错误状态、记录错误并抛出异常。

##### merge_retrieved_info

召回信息合并节点位于 backend/app/agent/nodes/merge_retrieved_info.py，用于将字段、指标和字段取值三路召回结果整理为后续节点可使用的表信息及指标信息。

合并过程包括：

1. 以召回字段为基础，建立按字段编号索引的信息集合。
2. 遍历召回指标的关联字段，从元数据库补充尚未召回的字段信息。
3. 将召回取值合并到对应字段的示例取值中；对应字段不存在时，先从元数据库读取字段信息。
4. 按所属表编号对字段分组。
5. 显式补充每张表的主键和外键字段，避免遗漏表关联所需的信息。
6. 读取各表的元数据信息，构造包含表描述及字段列表的表格状态。
7. 将召回指标整理为指标状态，返回表信息和指标信息。

backend/app/repositories/mysql/meta/meta_mysql_repository.py 提供按编号查询字段、按编号查询表，以及按表编号查询主键和外键字段的能力。

节点输出“合并召回信息”的进度，并记录合并后的表和指标；失败时输出错误状态并抛出异常。

##### filter_table

表格过滤节点位于 backend/app/agent/nodes/filter_table.py。

节点将用户问题和合并后的表信息输入表格过滤提示词与大模型。表信息以保留中文和字段顺序的 YAML 文本提供，模型结果以 JSON 解析。

根据模型返回的表及字段选择结果，移除未选中的表和字段，将过滤后的表信息写回状态。节点输出“过滤表格”的执行进度，并记录保留的表；失败时输出错误状态并抛出异常。

##### filter_metric

指标过滤节点位于 backend/app/agent/nodes/filter_metric.py。

节点将用户问题和指标信息输入指标过滤提示词与大模型。指标信息以 YAML 文本提供，模型结果以 JSON 解析。根据模型返回的指标选择结果，移除未选中的指标，将过滤后的指标信息写回状态。

节点输出“过滤指标”的执行进度，并记录保留的指标；失败时输出错误状态并抛出异常。

##### add_extra_context

额外上下文节点位于 backend/app/agent/nodes/add_extra_context.py。

节点以北京时间获取当前日期、星期和季度，并从数据仓库读取数据库版本及方言，将日期信息与数据库信息写入智能体状态，为 SQL 生成和校正提供环境依据。

backend/app/repositories/mysql/dw/dw_mysql_repository.py 提供数据库环境信息查询能力，并提供通过执行计划检查 SQL 的验证能力。

节点输出“添加额外上下文信息”的执行进度；失败时输出错误状态、记录错误并抛出异常。

##### generate_sql

SQL 生成节点位于 backend/app/agent/nodes/generate_sql.py。

节点读取用户问题、筛选后的表信息及指标信息、日期信息和数据库环境信息，将这些上下文输入 SQL 生成提示词与大模型。结构化上下文转换为 YAML 文本，模型输出按字符串解析，作为生成的 SQL 写入状态。

节点输出“生成SQL”的执行进度，并记录生成结果；失败时输出错误状态并抛出异常。

##### validate_sql

SQL 验证节点位于 backend/app/agent/nodes/validate_sql.py。

节点读取生成的 SQL，调用数据仓库 Repository，通过执行计划检查语句。验证成功时清空错误信息，并输出成功进度；捕获到 SQLAlchemy 数据库错误时，保存异常文本并输出错误进度，由工作流选择校正节点；其他异常向外传播并终止流程。

##### correct_sql

SQL 校正节点位于 backend/app/agent/nodes/correct_sql.py。

节点读取原 SQL 和验证错误，同时结合用户问题、表信息、指标信息、日期信息和数据库环境信息，调用 SQL 校正提示词与大模型。模型输出按字符串解析，替换状态中的 SQL。

节点输出“校正SQL”的执行进度，并记录校正结果；失败时输出错误状态并抛出异常。

##### execute_sql

SQL 执行节点位于 backend/app/agent/nodes/execute_sql.py。

节点调用数据仓库 Repository 执行状态中的 SQL。Repository 将每行查询记录转换为包含字段名与字段值的字典，形成结果列表。

执行成功后，先输出“执行SQL”的成功进度，再输出查询结果消息；失败时输出错误进度、记录错误并抛出异常。

相应的执行能力在 backend/app/repositories/mysql/dw/dw_mysql_repository.py 中提供。

#### 6.3.6 graph

智能体工作流定义于 backend/app/agent/graph.py，使用 LangGraph 的状态图，分别指定智能体状态结构与运行上下文结构，并注册各执行节点。

工作流关系如下：

1. 从开始节点进入关键词抽取。
2. 关键词抽取后，分别进入字段召回、字段取值召回和指标召回。
3. 三路召回结果进入召回信息合并。
4. 合并后分别进行表格过滤和指标过滤。
5. 过滤结果进入额外上下文补充。
6. 补充上下文后生成 SQL，再进行 SQL 验证。
7. 验证成功时直接执行 SQL；验证失败时先校正 SQL，再执行。
8. SQL 执行完成后结束工作流。

工作流中，校正节点直接连接执行节点。定义完成后，将状态图编译为可运行的工作流。

### 6.4 测试

工作流测试位于 backend/tests/test_agent_graph.py，检查节点组成、正常查询流程、SQL 校正路径和模型失败时的错误输出。节点的关键词抽取、召回、合并、筛选及 SQL 处理测试位于 backend/tests/test_agent_nodes.py。

## 7 API 接口

### 7.1 需求说明

本章旨在实现一个查询接口，用于接收用户查询，并实时响应工作流执行进度和查询结果。接口使用 FastAPI 框架编写，涉及的相关知识点如下：

- [流式响应](https://fastapi.org.cn/advanced/custom-response/#streamingresponse)。
- [SSE 协议](https://www.ruanyifeng.com/blog/2017/05/server-sent_events.html)。
- [生命周期事件](https://fastapi.org.cn/advanced/events/)。
- [中间件](https://fastapi.org.cn/tutorial/middleware/)。
- [依赖注入](https://fastapi.org.cn/tutorial/dependencies/)。

### 7.2 代码组织规划

API 模块各部分的职责如下：

- backend/app/main.py：FastAPI 应用入口。
- backend/app/api/routers/query_router.py：定义查询路由。
- backend/app/schemas/query_schema.py：定义请求体结构。
- backend/app/dependencies/query.py：组装查询接口依赖。
- backend/app/services/query_service.py：执行工作流并输出 SSE 事件。
- backend/app/core/lifespan.py：管理外部客户端的初始化和关闭。
- backend/app/core/context.py：定义请求上下文变量。
- backend/app/core/log.py：定义带请求编号的日志输出。

### 7.3 具体实现

#### 7.3.1 入口脚本

FastAPI 应用实例定义在 backend/app/main.py 中，并注册查询路由、生命周期函数和请求中间件。后端通过 Uvicorn 启动；Compose 中监听容器内的 8000 端口，由前端代理访问。

#### 7.3.2 查询接口

##### 接口定义

查询接口用于接收来自客户端的查询请求，并流式响应工作流的执行进度和查询结果。

接口在 backend/app/api/routers/query_router.py 中定义，路径为 /api/query，使用 POST 方法。请求体包含用户查询文本，接口通过依赖注入获取查询服务，并以 StreamingResponse 返回查询服务产生的数据流，响应媒体类型为 text/event-stream。

查询路由在 backend/app/main.py 中注册到 FastAPI 实例。

##### 接口实现

**QuerySchema**

请求体结构定义于 backend/app/schemas/query_schema.py，使用 Pydantic 模型，包含一个字符串类型的 query 字段，用于接收用户查询。

**QueryService**

查询服务定义于 backend/app/services/query_service.py，接收 Embedding 客户端、字段向量 Repository、指标向量 Repository、字段取值 Elasticsearch Repository、元数据库 Repository 和数据仓库 Repository。

收到查询后，服务将这些依赖组装为智能体运行上下文，以用户问题构造初始状态，并以自定义流式模式运行工作流。

工作流每产生一条消息，服务就将其转换为 JSON 文本，保留中文字符；不能直接进行 JSON 序列化的值转换为字符串。随后按 SSE 格式输出，以 data 字段承载消息，并用空行分隔事件。工作流发生异常时，将异常文本作为错误消息输出。

**依赖注入**

在 backend/app/dependencies/query.py 中定义查询接口所需的依赖项。

元数据库会话和数据仓库会话通过各自的会话工厂获取，并使用异步上下文管理器管理。Embedding 客户端由对应客户端管理器提供；Qdrant 和 Elasticsearch Repository 使用已有客户端构造；MySQL Repository 使用当前会话构造。最终将这些依赖组装为 QueryService，供查询路由使用。

#### 7.3.3 生命周期事件

本项目使用生命周期事件实现各外部存储系统客户端的初始化和关闭，相关逻辑位于 backend/app/core/lifespan.py。

FastAPI 应用启动前，初始化 Embedding、Qdrant、Elasticsearch、元数据库和数据仓库客户端。应用结束前，关闭 Qdrant、Elasticsearch、元数据库和数据仓库客户端。

生命周期处理函数在 backend/app/main.py 创建 FastAPI 实例时注册。

#### 7.3.4 中间件

本项目通过中间件为每个请求生成唯一的 request_id，并存储于 contextvar 中；日志系统在输出时自动附带该 request_id，从而在并发场景下实现精准的日志追踪与请求定位。

在 backend/app/core/context.py 中定义用于保存 request_id 的上下文变量。在 backend/app/main.py 中添加 HTTP 中间件，在调用路径处理函数之前生成唯一请求编号并写入上下文，然后继续处理请求并返回响应。

日志系统在输出前读取当前上下文中的请求编号，将其注入日志记录。调整后的日志格式包含时间、级别、request_id、模块、函数、行号和消息内容，控制台及文件输出继续由配置控制。

并发请求编号的隔离行为由 backend/tests/test_logging.py 中的测试验证。

### 7.4 测试

查询接口测试位于 backend/tests/test_query_api.py，覆盖请求格式校验、流式进度和结果、错误事件以及并发请求编号。

跨服务 HTTP 检查由 scripts/smoke.sh 实现，检查前端访问、后端查询路由和无效请求的响应状态。

## 8 前后端对接

### 8.1 启动前端项目

前端项目位于 frontend 目录，使用 Next.js、React 和 TypeScript，运行环境为 Node 22。

Docker Compose 提供开发和生产两种前端服务，通过根目录 Makefile 启动。开发服务挂载前端目录并支持热更新；生产服务使用 Next.js standalone 构建产物。

本地开发时，在 frontend 目录安装锁定的 npm 依赖，再启动开发服务器。

### 8.2 访问前端页面

Compose 环境的前端入口为 http://localhost:8080，本地前端开发服务器默认使用 http://localhost:3000。

聊天页面提交用户问题后，通过前端的 /api/query 接口转发到后端。代理地址由 API_BASE_URL 配置，默认指向 http://localhost:8000，Compose 中指向 http://backend:8000。

前端逐条读取 SSE 事件，更新执行步骤，展示查询结果表格或错误信息。
