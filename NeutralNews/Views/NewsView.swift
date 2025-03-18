//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI

struct NewsView: View {
    let news: News
    let relatedNews: [News]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(news.title)
                    .font(.title)
                    .fontWeight(.semibold)
                
                AsyncImage(url: URL(string: news.imageUrl ?? "")) { image in
                    image.image?
                        .resizable()
                        .scaledToFit()
                }
                .frame(maxWidth: .infinity)
                .clipShape(.rect(cornerRadius: 16))
                
                Text(news.description)
            }
            .padding()
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(relatedNews) { new in
                        MediaHeadlineView(news: new)
                    }
                }
                .padding(.leading, 16)
            }
        }
        .scrollBounceBehavior(.basedOnSize)
    }
}

#Preview {
    NewsView(news: .mock, relatedNews: [.mock, .mock, .mock])
}
