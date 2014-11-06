% title = None
% rebase('base.tpl', title=title, canonical=False)

<div>
<h3>Deeds signed by {{otc_name}}</h3>
<ul>
  <li>otc name: <a href="{{otc_url(otc_name)}}">{{otc_name}}</a>
  <li>fingerprint: {{fingerprint}} </li>
  <li>keyid: {{fingerprint[24:]}}</li>
  <li>deeds: {{num_deeds}}</li>
</ul>
</div>

<div class="deeds">
% if deeds:
  <table>
    <tr><td>created</td><td>link</td><td>bundled</td><td>bundle</td><td>title</td></tr>
  % for deed in deeds:
    <tr>
      <td>{{date(deed['created_at'])}}</td>
      <td><a href="{{deed_url(deed['b58_hash'])}}">{{deed['b58_hash']}}</a></td>
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
% else:
<p>No deeds found.</p>
% end
</div>
