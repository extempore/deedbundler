<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>deeds signed by {{otc_name}}</title>
    <author>{{otc_name}}</author>
    <updated>{{date(updated)}}</updated>
% for deed in deeds:
    <item>
      <title>{{deed['b58_hash']}}</title>
      <link>{{deed_url(deed['b58_hash'])}}</link>
      <pubDate>{{date(deed['created_at'])}}</pubDate>
      <author>{{deed['fingerprint']}}</author>
      <guid>{{deed['b58_hash']}}</guid>
      <description>{{deed['title'] or ''}}</description>
    </item>
% end
  </channel>
</rss>
