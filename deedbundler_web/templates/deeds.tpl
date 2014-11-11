% title = 'Deeds'
% rebase('base.tpl', title=title, canonical=False)

<div class="deeds">
<h2>Deeds</h2>
  <table>
    <tr>
      <td>created</td>
      <td>link</td>
      <td>name</td>
      <td>bundled</td>
      <td>bundle</td>
      <td>title</td></tr>
  % for deed in deeds:
    <tr>
      <td>{{date(deed['created_at'])}}</td>
      <td><a href="{{deed_url(deed['b58_hash'])}}">{{deed['b58_hash']}}</a></td>
      <td>{{deed['otc_name']}}</td>
      <td>{{date(deed['bundled_at']) if deed['bundled_at'] else 'pending'}}</td>
      % if deed['bundle_address']:
      <td><a href="{{bundle_url(deed['bundle_address'])}}">{{deed['bundle_address'][:8]}}</a></td>
      % else:
      <td>n/a</td>
      % end
      <td>{{deed['title'] or ''}}</td>
    </tr>
  % end
  </table>
</div>

<div class="pagination">
<p>Page: 
% for i, link in enumerate(links, 1):
  % if i == page:
  <em>({{i}})</em> | 
  % else:
  <a href="{{link}}">{{i}}</a> | 
  % end
% end
</p>
</div>
