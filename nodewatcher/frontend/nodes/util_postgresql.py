from django.db import models, connections, connection, DEFAULT_DB_ALIAS
from django.db.models.sql.constants import LOOKUP_SEP
from django.conf import settings
from frontend.nodes import ipcalc

# Quote name
qn = connection.ops.quote_name

class IPQuerySet(models.query.QuerySet):
  """
  An extended query set that supports IP4 operations.
  """
  def ip_filter(self, **kwargs):
    """
    Performs an IP4 lookup.
    """
    connection = connections[self._db or DEFAULT_DB_ALIAS]
    where_opts = []
    for key, value in kwargs.iteritems():
      field, op = key.split(LOOKUP_SEP)
      field_obj = self.model._meta.get_field_by_name(field)[0]
      value = field_obj.get_db_prep_lookup('exact', value, connection = connection)[0]
      field = "%s.%s" % (self.model._meta.db_table, field)
      
      if op == 'contains':
        where_opts.append('%s >>= %s' % (field, value))
      elif op == 'contained_in':
        where_opts.append('%s <<= %s' % (field, value))
      elif op == 'conflicts':
        where_opts.append('(%s <<= %s OR %s >>= %s)' % (field, value, field, value))
      else:
        raise TypeError('Operation %s not supported.' % op)
    
    return self.extra(where = where_opts)

class IPManager(models.Manager):
  """
  A manager for supporting fast IPv4 lookups via ip4r PostgreSQL
  extension.
  """
  def get_query_set(self):
    """
    Returns a modified query set that supports IP4 operations.
    """
    return IPQuerySet(self.model)
  
  def ip_filter(self, *args, **kwargs):
    """
    Shortcut for queryset's ip_filter.
    """
    return self.get_query_set().ip_filter(*args, **kwargs)

class IPField(models.Field):
  """
  A custom ip4r field.
  """
  def db_type(self, connection):
    """
    Returns the database field type name.
    """
    return 'ip4r'
  
  def get_db_prep_value(self, value, connection, prepared = False):
    """
    Properly formats a value for this field.
    """
    try:
      ipcalc.IP(value)
    except ValueError:
      raise ValueError('Field %s requires a valid IP address!' % self.column)
    
    return "ip4r('%s')" % value
  
  def get_db_prep_save(self, value, connection):
    """
    Properly formats a value for this field.
    """
    try:
      ipcalc.IP(value)
    except ValueError:
      raise ValueError('Field %s requires a valid IP address!' % self.column)
    
    return value
  
  def get_placeholder(self, value, connection):
    """
    Returns a proper placeholder for the database value.
    """
    return "ip4r(%s)"
  
  def get_db_prep_lookup(self, lookup_type, value, connection, prepared = False):
    """
    Prepares this field for a database lookup.
    """
    if lookup_type != 'exact':
      raise TypeError('Lookup type %s not supported.' % lookup_type)
    
    return [self.get_db_prep_value(value, connection = connection)]
  
  def post_create_sql(self, style, db_table):
    """
    Returns SQL that will be executed after the model has been created.
    """
    post_sql = (
      style.SQL_KEYWORD('CREATE ') +
      style.SQL_KEYWORD('INDEX ') +
      style.SQL_TABLE(qn('%s_%s_ip4' % (db_table, self.column))) + ' ' +
      style.SQL_KEYWORD('ON ') +
      style.SQL_TABLE(qn(db_table)) + ' ' +
      style.SQL_KEYWORD('USING ') +
      style.SQL_TABLE('gist') + '(' +
      style.SQL_FIELD(qn(self.column)) + ');'
    )
    
    return (post_sql,)

def queryset_by_ip(queryset, field_name, *sort_first):
  """
  Sorts the `query` by `field_name` where it represents some IP typed field. It can first sorts
  lexicographically by `sort_first` fields, which it sorts normally.
  
  On PostgreSQL databases we simply use Django's `order_by` on queryset.
  """
  sort = list(sort_first)
  sort.append(field_name)
  return queryset.order_by(*sort)

