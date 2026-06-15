"""
AI Service — Knowledge Graph Module
Neo4j: Lưu trữ đồ thị hành vi người dùng và cập nhật trọng số theo thời gian thực.
"""
import logging
from typing import List, Optional
from neo4j import GraphDatabase, exceptions as neo4j_exc

logger = logging.getLogger(__name__)


class Neo4jKnowledgeGraph:
    """
    Kết nối và tương tác với Neo4j để quản lý đồ thị tri thức hành vi người dùng.

    Schema trong Neo4j:
        (:User {id}) -[:INTERACTED_WITH {weight, last_updated}]-> (:Product {id})
        (:Product {id}) -[:BELONGS_TO]-> (:Category {name, slug})
    """

    WEIGHT_MAP = {
        "view":        1,
        "add_to_cart": 3,
        "purchase":    5,
        "remove":     -1,
    }

    def __init__(self, uri: str, user: str, password: str):
        self._uri      = uri
        self._user     = user
        self._password = password
        self._driver   = None
        self._connect()

    def _connect(self):
        try:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password)
            )
            self._driver.verify_connectivity()
            logger.info("[Neo4j] Connected to Knowledge Graph ✓")
            self._ensure_constraints()
        except Exception as e:
            logger.warning(f"[Neo4j] Connection failed: {e}. Graph features disabled.")
            self._driver = None

    def _ensure_constraints(self):
        """Tạo constraint và index khi lần đầu khởi động."""
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User)    REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.slug IS UNIQUE",
        ]
        with self._driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception:
                    pass  # Ignore if already exists

    @property
    def is_available(self) -> bool:
        return self._driver is not None

    def close(self):
        if self._driver:
            self._driver.close()

    # ── Ghi dữ liệu ──────────────────────────────────────────────

    def update_interaction_weight(self, user_id: int, product_id: int, action_type: str):
        """
        Cập nhật trọng số tương tác trên đồ thị dựa trên hành vi người dùng.
        Nếu quan hệ chưa tồn tại → Tạo mới với weight ban đầu.
        Nếu đã tồn tại → Cộng dồn weight.
        """
        if not self.is_available:
            return

        weight = self.WEIGHT_MAP.get(action_type, 1)
        query = """
        MERGE (u:User {id: $user_id})
        MERGE (p:Product {id: $product_id})
        MERGE (u)-[r:INTERACTED_WITH]->(p)
        ON CREATE SET r.weight = $weight, r.last_updated = timestamp(), r.action_count = 1
        ON MATCH  SET r.weight = r.weight + $weight,
                      r.last_updated = timestamp(),
                      r.action_count = r.action_count + 1
        """
        try:
            with self._driver.session() as session:
                session.run(query, user_id=user_id, product_id=product_id, weight=weight)
            logger.debug(f"[Neo4j] Interaction: user={user_id}, product={product_id}, action={action_type}")
        except Exception as e:
            logger.error(f"[Neo4j] update_interaction_weight failed: {e}")

    def upsert_product(self, product_id: int, name: str, category_slug: str, category_name: str):
        """
        Đồng bộ node Product và Category từ Product Service sang Neo4j.
        Gọi khi rebuild index hoặc có sản phẩm mới.
        """
        if not self.is_available:
            return

        query = """
        MERGE (p:Product {id: $product_id})
        SET   p.name = $name

        MERGE (c:Category {slug: $category_slug})
        SET   c.name = $category_name

        MERGE (p)-[:BELONGS_TO]->(c)
        """
        try:
            with self._driver.session() as session:
                session.run(query,
                    product_id=product_id,
                    name=name,
                    category_slug=category_slug,
                    category_name=category_name
                )
        except Exception as e:
            logger.error(f"[Neo4j] upsert_product failed: {e}")

    def bulk_upsert_products(self, products: List[dict]):
        """Đồng bộ hàng loạt sản phẩm. Gọi khi startup hoặc rebuild."""
        if not self.is_available or not products:
            return
        for p in products:
            self.upsert_product(
                product_id=p.get("id"),
                name=p.get("name", ""),
                category_slug=p.get("category_slug") or (p.get("category") or {}).get("slug", "unknown"),
                category_name=p.get("category_name") or (p.get("category") or {}).get("name", "Unknown"),
            )
        logger.info(f"[Neo4j] Bulk-upserted {len(products)} products into graph.")

    # ── Đọc dữ liệu ──────────────────────────────────────────────

    def get_user_favorite_categories(self, user_id: int, limit: int = 3) -> List[str]:
        """
        Truy vấn đồ thị để lấy danh mục sản phẩm mà user tương tác nhiều nhất.
        Trả về list tên danh mục, sắp xếp theo tổng trọng số giảm dần.
        """
        if not self.is_available:
            return []

        query = """
        MATCH (u:User {id: $user_id})-[r:INTERACTED_WITH]->(p:Product)-[:BELONGS_TO]->(c:Category)
        RETURN c.name AS category, SUM(r.weight) AS total_weight
        ORDER BY total_weight DESC
        LIMIT $limit
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, user_id=user_id, limit=limit)
                return [record["category"] for record in result]
        except Exception as e:
            logger.error(f"[Neo4j] get_user_favorite_categories failed: {e}")
            return []

    def get_similar_users_products(self, user_id: int, limit: int = 5) -> List[int]:
        """
        Collaborative Filtering nhẹ: Lấy sản phẩm từ người dùng có cùng sở thích.
        Tìm users đã mua sản phẩm giống nhau → Gợi ý sản phẩm mà user hiện tại chưa mua.
        """
        if not self.is_available:
            return []

        query = """
        MATCH  (me:User {id: $user_id})-[:INTERACTED_WITH]->(p:Product)
               <-[:INTERACTED_WITH]-(similar:User)
        WHERE  similar.id <> $user_id
        WITH   me, similar, COUNT(p) AS shared_products
        ORDER  BY shared_products DESC
        LIMIT  3
        MATCH  (similar)-[r:INTERACTED_WITH]->(recommend:Product)
        WHERE  NOT (me)-[:INTERACTED_WITH]->(recommend)
        RETURN recommend.id AS product_id, SUM(r.weight) AS score
        ORDER  BY score DESC
        LIMIT  $limit
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, user_id=user_id, limit=limit)
                return [record["product_id"] for record in result]
        except Exception as e:
            logger.error(f"[Neo4j] get_similar_users_products failed: {e}")
            return []

    def get_user_interaction_summary(self, user_id: int) -> dict:
        """Tóm tắt hành vi người dùng từ đồ thị để inject vào prompt."""
        categories = self.get_user_favorite_categories(user_id, limit=3)
        similar_products = self.get_similar_users_products(user_id, limit=5)
        return {
            "favorite_categories": categories,
            "collaborative_products": similar_products,
        }
