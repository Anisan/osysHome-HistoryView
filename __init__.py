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
        if op == 'delete':
            id = request.args.get("id",None)
            with session_scope() as session:
                session.query(History).filter(History.id==id).delete()
                session.commit()
                return redirect(f'{self.name}?object={object_id}&name={name}')

        obj = Object.query.where(Object.id == object_id).one_or_none()
        
        return render_template('history.html', object=obj, name=name)

