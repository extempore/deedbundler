% title = 'Bundles'
% rebase('base.tpl', title=title, canonical=False)

<div class="bundles">
<h2>Bundles</h2>
  <table>
    <tr>
      <td>created</td>
      <td>link</td>
      <td>deeds</td>
      <td>confirmed</td>
      <td>tx</td>
    </tr>
  % for bundle in bundles:
    <tr>
      <td>{{date(bundle['created_at'])}}</td>
      <td><a href="{{bundle_url(bundle['address'])}}">{{bundle['address']}}</a></td>
      <td>{{bundle['num_deeds']}}</td>
    % conf = bundle['confirmed_at']
      <td>{{date(conf) if conf else 'n/a'}}</td>
      <td>(<a href="https://blockchain.info/tx/{{bundle['txid']}}">tx</a>)</td>
    </tr>
  % end
  </table>
</div>

<div class="pagination">
<p>Page: 
% for i, link in enumerate(links):
  % if i == page:
  <em>({{i}})</em> | 
  % else:
  <a href="{{link}}">{{i}}</a> | 
  % end
% end
</p>
</div>
