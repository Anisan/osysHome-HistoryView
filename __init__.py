from flask import render_template, redirect
from app.core.main.BasePlugin import BasePlugin
from app.database import session_scope
from app.authentication.handlers import handle_admin_required
from app.core.models.Clasess import Object,Value, History
from sqlalchemy import desc

class HistoryView(BasePlugin):

    def __init__(self,app):
        super().__init__(app,__name__)
        self.title = "History"
        self.description = """History viewer"""
        self.category = "System"
    
    def initialization(self):
        pass

    def admin(self, request):
        op = request.args.get("op",None)
        object_id = int(request.args.get("object",0))
        name = request.args.get("name",None)
        page = int(request.args.get("page", 0))
        if op == 'delete':
            id = request.args.get("id",None)
            with session_scope() as session:
                session.query(History).filter(History.id==id).delete()
                session.commit()
                return redirect(f'{self.name}?object={object_id}&name={name}&page={page}')

        per_page = 30
        obj = Object.query.where(Object.id == object_id).one_or_none()
        value = Value.query.where(Value.name == name, Value.object_id == object_id).one_or_none()
        history = []
        if value:
            history = History.query.where(History.value_id == value.id).order_by(desc(History.added)).paginate(page=page, per_page=per_page, error_out=False)

        return render_template('history.html', object=obj, name=name, data=history.items, total=history.total, page=page, pages=history.pages)

